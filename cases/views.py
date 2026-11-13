from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince, timeuntil

from . import ai, alerts, reporter_messages
from .forms import (
    FeedbackForm, LetterForm, ReassignForm, ReportForm, ReportUpdateForm, RoleForm, TriageForm, VisitForm,
)
from .models import (
    OPEN_STATUSES, PRIORITY_RANK, UNHAPPY_FOLLOW_UP, UNHAPPY_SCORE, Alert, AlertRead, Case, CaseChange, Category, Communication, Officer, Profile, ReportPhoto, ReportUpdate, Role, Status,
    Language, Priority, SLARule, Team, get_role,
)
from .permissions import can_view_case, role_required

ALL_ROLES = [r.value for r in Role]
HANDLERS = [Role.HANDLER, Role.MANAGER]


def display_name(user):
    return user.get_full_name() or user.username


# ---------- Home: different content for each role ----------

def home(request):
    role = get_role(request.user)
    ctx = {}
    if role == Role.REPORTER:
        mine = Case.objects.filter(reporter_user=request.user)
        ctx['my_open'] = mine.filter(status__in=OPEN_STATUSES + [Status.RESOLVED])
        ctx['my_closed'] = mine.filter(status__in=[Status.CLOSED, Status.DUPLICATE]).order_by('-date_closed')[:5]
        ctx['awaiting_feedback'] = [c for c in mine.filter(status=Status.CLOSED, satisfaction__isnull=True)
                                    if c.feedback_open]
    elif role == Role.HANDLER:
        ctx['triage'] = sorted(Case.objects.filter(status=Status.NEW).select_related('ai_category__default_team'),
                               key=lambda c: (-PRIORITY_RANK.get(c.ai_priority, 0), c.date_reported))
        ctx['replies'] = Case.objects.filter(status=Status.RESOLVED).count()
        ctx['unhappy'] = _unhappy_reporters().count()
        ctx['overdue'] = Case.objects.filter(status__in=OPEN_STATUSES, sla_due__lt=timezone.now()).count()
    elif role == Role.OFFICER:
        officer = getattr(request.user, 'officer', None)
        ctx['officer'] = officer
        if officer:
            ctx['jobs'] = Case.objects.filter(
                assigned_officer=officer, status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).order_by('sla_due')
            ctx['team_unassigned'] = Case.objects.filter(
                assigned_team=officer.team, assigned_officer__isnull=True,
                status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).count()
    elif role == Role.MANAGER:
        ctx.update(_dashboard_stats())
    return render(request, 'cases/home.html', ctx)


# ---------- 1. Report ----------

@login_required
def report(request):
    if request.method == 'POST':
        form = ReportForm(request.POST, request.FILES)
        if form.is_valid():
            case = form.save(commit=False)
            case.reporter_user = request.user
            case.reporter_name = display_name(request.user)
            case.reporter_email = request.user.email
            case.save()
            for photo in form.cleaned_data['photo']:
                ReportPhoto.objects.create(case=case, image=photo)
            suggestion = ai.triage(case)
            case.ai_category = suggestion['category']
            case.ai_priority = suggestion['priority']
            case.ai_summary = suggestion['summary']
            case.ai_reasoning = suggestion['reasoning']
            case.ai_confidence = suggestion['confidence']
            case.ai_duplicate_candidate = suggestion['duplicate']
            case.save()
            reporter_messages.received(case)
            messages.success(request, f'Thank you - your report has been received. Your reference is {case.reference}.')
            return redirect('track_case', ref=case.reference)
    else:
        form = ReportForm()
    buildings = Case.objects.values_list('building', flat=True).distinct()
    return render(request, 'cases/report.html', {'form': form, 'buildings': buildings})


@login_required
def my_reports(request):
    """Every report the signed-in user has made, newest first. Staff can report issues too."""
    reports = list(Case.objects.filter(reporter_user=request.user).order_by('-date_reported').annotate(
        new_messages=Count('communications', filter=Q(communications__date_sent__isnull=False,
                                                      communications__read_at__isnull=True))))
    open_count = sum(c.status in OPEN_STATUSES for c in reports)
    to_rate = [c for c in reports if c.can_give_feedback(request.user) and c.satisfaction is None]
    # Only the statuses in the list, in the order a report moves through them, for the "Status" filter
    statuses = [(value, label) for value, label in Status.choices if any(c.status == value for c in reports)]
    return render(request, 'cases/my_reports.html', {
        'reports': reports, 'open_count': open_count, 'to_rate': {c.pk for c in to_rate},
        'statuses': statuses, 'new_total': sum(c.new_messages for c in reports),
    })


@login_required
def track(request):
    ref = request.GET.get('ref', '').strip().upper()
    if ref:
        case = Case.objects.filter(reference=ref).first()
        if case and can_view_case(request.user, case):
            return redirect('track_case', ref=ref)
        messages.error(request, f'We could not find a report with reference {ref} on your account.')
    return render(request, 'cases/track_search.html')


@login_required
def track_case(request, ref):
    case = get_object_or_404(Case, reference=ref)
    if not can_view_case(request.user, case):
        raise PermissionDenied

    # The reporter can add more details and photos until the case is closed
    update_form = ReportUpdateForm() if case.can_add_details(request.user) else None
    if request.method == 'POST' and 'add_details' in request.POST:
        if update_form is None:
            raise PermissionDenied  # not the reporter, or the case is closed or merged
        update_form = ReportUpdateForm(request.POST, request.FILES)
        if update_form.is_valid():
            update = ReportUpdate.objects.create(case=case, author=request.user,
                                                 text=update_form.cleaned_data['text'].strip())
            for photo in update_form.cleaned_data['photo']:
                ReportPhoto.objects.create(case=case, update=update, image=photo)
            messages.success(request, 'Thank you - your extra details have been added to '
                                      f'{case.reference}. The team working on it can see them now.')
            return redirect(f"{reverse('track_case', args=[case.reference])}#updates")
        return _render_track(request, case, None, update_form)

    feedback_form = None
    if case.can_give_feedback(request.user):
        if request.method == 'POST':
            feedback_form = FeedbackForm(request.POST, instance=case)
            if feedback_form.is_valid():
                feedback_form.save()
                messages.success(request, 'Thank you for your feedback. You can change it until '
                                          f'{timezone.localtime(case.feedback_deadline):%A %d %B}.')
                return redirect('track_case', ref=case.reference)
        else:
            feedback_form = FeedbackForm(instance=case)
    elif request.method == 'POST':
        raise PermissionDenied  # not the reporter, or the 14-day feedback window has closed
    return _render_track(request, case, feedback_form, update_form)


def _render_track(request, case, feedback_form, update_form):
    # Newest message first. Ones the reporter hasn't seen are marked "New" this time, then count as read.
    sent = list(case.communications.filter(date_sent__isnull=False).order_by('-date_sent', '-pk'))
    for m in sent:
        m.is_new = m.read_at is None
    if case.reporter_user_id == request.user.id and any(m.is_new for m in sent):
        Communication.objects.filter(pk__in=[m.pk for m in sent if m.is_new]).update(read_at=timezone.now())
    updates = case.updates.prefetch_related('photos')
    return render(request, 'cases/track.html', {
        'case': case, 'sent': sent, 'feedback_form': feedback_form, 'update_form': update_form,
        'updates': updates,
    })


# ---------- 2. Triage and route (case handler) ----------

def _unhappy_reporters():
    """Recently closed cases where the reporter gave a low score, for handlers to follow up."""
    return (Case.objects.filter(status=Status.CLOSED, satisfaction__lte=UNHAPPY_SCORE,
                                date_closed__gte=timezone.now() - UNHAPPY_FOLLOW_UP)
            .select_related('assigned_team').order_by('satisfaction', '-date_closed'))


@role_required(*HANDLERS)
def triage_queue(request):
    new_cases = sorted(
        Case.objects.filter(status=Status.NEW).select_related('ai_category__default_team', 'ai_duplicate_candidate'),
        key=lambda c: (-PRIORITY_RANK.get(c.ai_priority, 0), c.date_reported),
    )
    awaiting_reply = Case.objects.filter(status=Status.RESOLVED).select_related('assigned_team')
    in_flight = Case.objects.filter(status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).select_related(
        'assigned_team', 'assigned_officer').order_by('sla_due')
    # Priorities the AI suggested, and buildings, for cases waiting for triage: the
    # "Priority" and "Location" filters only list what's in the queue
    triage_priorities = [(PRIORITY_RANK[value], label) for value, label in Priority.choices
                         if any(c.ai_priority == value for c in new_cases)]
    triage_buildings = sorted({c.building for c in new_cases if c.building}, key=str.lower)
    # The same for cases with teams: priorities, teams and officers that are in the "With teams" list
    in_flight = list(in_flight)
    teams_priorities = [(PRIORITY_RANK[value], label) for value, label in Priority.choices
                        if any(c.priority == value for c in in_flight)]
    teams_names = sorted({c.assigned_team.name for c in in_flight if c.assigned_team}, key=str.lower)
    teams_officers = sorted({c.assigned_officer.name for c in in_flight if c.assigned_officer}, key=str.lower)
    teams_unassigned = any(c.assigned_officer_id is None for c in in_flight)
    # Teams and reply languages in the "Fixed - reply needed" list, for its filters
    awaiting_reply = list(awaiting_reply)
    reply_teams = sorted({c.assigned_team.name for c in awaiting_reply if c.assigned_team}, key=str.lower)
    reply_languages = [(code, label) for code, label in Language.choices
                       if any(c.preferred_language == code for c in awaiting_reply)]
    # Reporters in the "Unhappy reporters" list, for its "Reporter" filter
    unhappy = list(_unhappy_reporters())
    unhappy_names = sorted({c.reporter_name for c in unhappy if c.reporter_name}, key=str.lower)
    return render(request, 'cases/triage_queue.html', {
        'new_cases': new_cases, 'awaiting_reply': awaiting_reply, 'in_flight': in_flight,
        'unhappy': unhappy, 'unhappy_names': unhappy_names, 'triage_priorities': triage_priorities,
        'triage_buildings': triage_buildings, 'teams_priorities': teams_priorities,
        'teams_names': teams_names, 'teams_officers': teams_officers, 'teams_unassigned': teams_unassigned,
        'reply_teams': reply_teams, 'reply_languages': reply_languages,
    })


@role_required(*HANDLERS)
def triage_case(request, ref):
    case = get_object_or_404(Case, reference=ref)
    if case.status != Status.NEW:
        return redirect('case_detail', ref=ref)
    approver = display_name(request.user)

    if request.method == 'POST':
        form = TriageForm(request.POST, case=case)
        if form.is_valid():
            d = form.cleaned_data
            case.triaged_by = approver
            case.date_acknowledged = timezone.now()
            if d['duplicate_of']:
                case.duplicate_of = d['duplicate_of']
                case.status = Status.DUPLICATE
                case.date_closed = timezone.now()
                case.ai_suggestion_accepted = case.ai_duplicate_candidate_id == d['duplicate_of'].id
                case.save()
                reporter_messages.merged(case, approver)
                messages.success(request, f'{case.reference} merged into {case.duplicate_of.reference}.')
                return redirect('triage_queue')

            case.category = d['category']
            case.priority = d['priority']
            case.assigned_team = d['team']
            case.assigned_officer = d['officer']
            case.status = Status.ASSIGNED
            case.ai_suggestion_accepted = (
                case.category_id == case.ai_category_id and case.priority == case.ai_priority)
            case.apply_sla()
            case.save()
            reporter_messages.routed(case, approver)
            alert = alerts.alert_routed(case, request)
            messages.success(request, f'{case.reference} sent to {case.assigned_team}.{_alert_note(alert)}')
            return redirect('triage_queue')
    else:
        form = TriageForm(case=case, initial={
            'team': case.ai_category.default_team if case.ai_category else None,
            'category': case.ai_category,
            'priority': case.ai_priority,
        })
    return render(request, 'cases/triage_case.html', {'case': case, 'form': form, 'by_team': _by_team()})


def _by_team():
    """Category and officer ids for each team, so the page can narrow those lists to the chosen team."""
    by_team = {
        'category': {t: [] for t in Team.objects.values_list('id', flat=True)},
        'officer': {t: [] for t in Team.objects.values_list('id', flat=True)},
    }
    for cat_id, team_id in Category.objects.values_list('id', 'default_team_id'):
        if team_id:
            by_team['category'][team_id].append(cat_id)
    for officer_id, team_id in Officer.objects.values_list('id', 'team_id'):
        by_team['officer'][team_id].append(officer_id)
    return by_team


@role_required(*HANDLERS)
def case_detail(request, ref):
    case = get_object_or_404(Case, reference=ref)
    return render(request, 'cases/case_detail.html', {'case': case})


# Cases can be re-routed after triage until the work is done
REASSIGNABLE = [Status.ASSIGNED, Status.IN_PROGRESS]


@role_required(*HANDLERS)
def reassign_case(request, ref):
    case = get_object_or_404(Case, reference=ref)
    if case.status == Status.NEW:
        return redirect('triage_case', ref=ref)
    if case.status not in REASSIGNABLE:
        messages.info(request, f'{case.reference} is {case.get_status_display().lower()}, so its priority '
                               f'and assignment can no longer be changed.')
        return redirect('case_detail', ref=ref)

    if request.method == 'POST':
        form = ReassignForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            before = {'priority': case.get_priority_display() or '-', 'team': str(case.assigned_team or '-'),
                      'category': str(case.category or '-'),
                      'officer': case.assigned_officer.name if case.assigned_officer else 'Unassigned'}
            priority_changed = d['priority'] != case.priority
            old_officer = case.assigned_officer
            old_team_id, old_due = case.assigned_team_id, case.sla_due
            case.priority = d['priority']
            case.assigned_team = d['team']
            case.category = d['category']
            case.assigned_officer = d['officer']
            after = {'priority': case.get_priority_display(), 'team': str(case.assigned_team),
                     'category': str(case.category),
                     'officer': case.assigned_officer.name if case.assigned_officer else 'Unassigned'}
            lines = [f'{field.capitalize()}: {before[field]} → {after[field]}'
                     for field in ('priority', 'team', 'category', 'officer') if before[field] != after[field]]
            if not lines:
                messages.info(request, f'Nothing was changed on {case.reference}.')
                return redirect('case_detail', ref=ref)
            if priority_changed:
                case.apply_sla()  # the target date follows the priority, counted from when it was reported
                if case.sla_due != old_due:
                    lines.append(f'SLA due: {_when(old_due)} → {_when(case.sla_due)}')
            case.save()
            CaseChange.objects.create(case=case, changed_by=display_name(request.user),
                                      summary='\n'.join(lines), reason=d['reason'])
            alert = alerts.alert_changed(case, lines, old_officer, request)
            reporter_messages.changed(case, display_name(request.user), new_due=case.sla_due != old_due,
                                      new_team=case.assigned_team_id != old_team_id)
            messages.success(request, f'{case.reference} updated.{_alert_note(alert)}')
            return redirect('case_detail', ref=ref)
    else:
        form = ReassignForm(initial={'priority': case.priority, 'team': case.assigned_team,
                                     'category': case.category, 'officer': case.assigned_officer})
    return render(request, 'cases/reassign_case.html', {'case': case, 'form': form, 'by_team': _by_team()})


def _alert_note(alert):
    """The end of the confirmation message, saying who was alerted."""
    if alert is None:
        return ''
    if not alert.delivered:
        return ' The alert email could not be sent - please contact the team directly.'
    return f' Alert sent to {alert.recipients}.'


def _when(moment):
    return f'{timezone.localtime(moment):%d %b %Y, %H:%M}' if moment else '-'


# ---------- 3 & 4. Attend, investigate, record outcome (field officer) ----------

def _current_officer(request):
    officer = getattr(request.user, 'officer', None)
    if officer is None:
        messages.error(request, 'Your account is not linked to a field officer record yet. Ask a manager.')
    return officer


@role_required(Role.OFFICER)
def officer_cases(request):
    officer = _current_officer(request)
    cases, team_unassigned = [], []
    if officer:
        cases = Case.objects.filter(
            assigned_officer=officer, status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).order_by('sla_due')
        team_unassigned = Case.objects.filter(
            assigned_team=officer.team, assigned_officer__isnull=True,
            status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).order_by('sla_due')
    # Buildings and priorities the officer has jobs in, for the "Location" and "Priority" filters
    jobs = [*cases, *team_unassigned]
    buildings = sorted({c.building for c in jobs if c.building}, key=str.lower)
    priorities = [(PRIORITY_RANK[value], label) for value, label in Priority.choices
                  if any(c.priority == value for c in jobs)]
    return render(request, 'cases/officer_cases.html', {
        'officer': officer, 'cases': cases, 'team_unassigned': team_unassigned,
        'buildings': buildings, 'priorities': priorities,
    })


@role_required(Role.OFFICER)
def officer_case(request, ref):
    case = get_object_or_404(Case, reference=ref)
    officer = _current_officer(request)
    if not officer:
        return redirect('index')
    # Officers can only work on their own jobs or unassigned jobs in their team
    if case.assigned_team_id != officer.team_id or case.assigned_officer_id not in (None, officer.id):
        raise PermissionDenied

    if request.method == 'POST' and 'take' in request.POST:
        case.assigned_officer = officer
        case.save()
        messages.success(request, f'{case.reference} is now assigned to you.')
        return redirect('officer_case', ref=ref)

    if request.method == 'POST':
        if case.assigned_officer_id != officer.id:
            raise PermissionDenied
        # Only open jobs take visits. A visit sent from an old tab, or a second click on Save,
        # would otherwise reopen a fixed or closed job and spoil its fix record.
        if case.status not in (Status.ASSIGNED, Status.IN_PROGRESS):
            state = {Status.RESOLVED: 'marked as fixed', Status.CLOSED: 'closed',
                     Status.DUPLICATE: 'merged as a duplicate'}.get(case.status, 'not open for visits')
            messages.info(request, f'{case.reference} is already {state}, so no visit was recorded.')
            return redirect('officer_cases')
        form = VisitForm(request.POST, request.FILES)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.case = case
            visit.officer = officer
            visit.ai_summary = ai.summarise_visit(visit.note, visit.fixed, visit.action)
            visit.save()
            if visit.fixed:
                case.status = Status.RESOLVED
                case.date_resolved = timezone.now()
                case.first_time_fix = case.visits.count() == 1
                messages.success(request, f'{case.reference} marked as fixed. The case handler will send the reply.')
            else:
                case.status = Status.IN_PROGRESS
                messages.success(request, f'Visit recorded. {case.reference} stays open for a follow-up.')
            case.save()
            reporter_messages.visited(case, visit)
            return redirect('officer_cases')
    else:
        form = VisitForm()
    return render(request, 'cases/officer_case.html', {'case': case, 'form': form, 'officer': officer})


@role_required(Role.OFFICER)
def alerts_inbox(request):
    """Alerts sent to this officer by name or to their team's inbox, newest first, with unread ones marked."""
    officer = _current_officer(request)
    if not officer:
        return redirect('index')
    visible = Alert.for_officer(officer)
    show_unread = request.GET.get('show') == 'unread'
    back = reverse('alerts') + ('?show=unread' if show_unread else '')

    if request.method == 'POST':
        if 'all' in request.POST:
            chosen = visible.exclude(reads__user=request.user)
        else:
            chosen = visible.filter(pk=request.POST.get('open') or request.POST.get('read') or 0)
        AlertRead.objects.bulk_create([AlertRead(alert=a, user=request.user) for a in chosen],
                                      ignore_conflicts=True)
        opened = chosen.select_related('case').first() if 'open' in request.POST else None
        if opened:
            return redirect('officer_case', ref=opened.case.reference)
        if 'all' in request.POST:
            messages.success(request, 'All alerts marked as read.')
        return redirect(back)

    items = list(visible.select_related('case', 'team').prefetch_related('officers'))
    read = set(AlertRead.objects.filter(user=request.user, alert__in=items).values_list('alert_id', flat=True))
    for a in items:
        a.unread = a.pk not in read
        a.to_you = any(o.pk == officer.pk for o in a.officers.all())
        a.intro = a.body.split('\n\n')[0]
        c = a.case
        # The job link only works while the job is open and still this officer's (or unassigned in their team)
        a.can_open = (c.status in (Status.ASSIGNED, Status.IN_PROGRESS) and c.assigned_team_id == officer.team_id
                      and c.assigned_officer_id in (None, officer.pk))
    all_total, unread_total = len(items), sum(a.unread for a in items)
    if show_unread:
        items = [a for a in items if a.unread]
    return render(request, 'cases/alerts.html', {
        'alerts': items, 'officer': officer, 'show_unread': show_unread,
        'unread_total': unread_total, 'all_total': all_total,
    })


# ---------- 5. Respond ----------

@role_required(*HANDLERS)
def outcome_letter(request, ref):
    case = get_object_or_404(Case, reference=ref)
    if case.status != Status.RESOLVED:
        return redirect('case_detail', ref=ref)
    letter = case.communications.filter(kind=Communication.Kind.OUTCOME).first()
    if letter is None:
        letter = Communication.objects.create(
            case=case, kind=Communication.Kind.OUTCOME, language=case.preferred_language,
            draft_text=ai.draft_outcome_letter(case), ai_drafted=True,
        )

    if request.method == 'POST':
        form = LetterForm(request.POST)
        if form.is_valid():
            letter.draft_text = form.cleaned_data['draft_text']
            letter.approved_by = display_name(request.user)
            letter.date_sent = timezone.now()
            letter.save()
            reporter_messages.email_reporter(letter)
            case.status = Status.CLOSED
            case.date_closed = timezone.now()
            case.save()
            messages.success(request, f'Outcome letter sent to {case.reporter_name}. {case.reference} is closed.')
            return redirect('triage_queue')
    else:
        form = LetterForm(initial={'draft_text': letter.draft_text})
    return render(request, 'cases/letter.html', {'case': case, 'form': form, 'letter': letter})


# ---------- 6. Review and improve (manager) ----------

def _pct(part, whole):
    return round(100 * part / whole) if whole else None


def _dashboard_stats():
    now = timezone.now()
    cases = Case.objects.exclude(status=Status.DUPLICATE)
    open_cases = cases.filter(status__in=OPEN_STATUSES)
    overdue = list(open_cases.filter(sla_due__lt=now).select_related('assigned_team', 'assigned_officer')
                   .order_by('sla_due'))

    resolved = cases.filter(date_resolved__isnull=False)
    ftf_known = resolved.exclude(first_time_fix__isnull=True)
    durations = [(c.date_resolved - c.date_reported).total_seconds() / 3600 for c in resolved]
    resolved_with_sla = [c for c in resolved if c.sla_due]
    acked = cases.filter(date_acknowledged__isnull=False, sla_acknowledge_due__isnull=False)
    triaged = Case.objects.exclude(ai_suggestion_accepted__isnull=True)
    scores = list(cases.filter(satisfaction__isnull=False).values_list('satisfaction', flat=True))

    return {
        'total': cases.count(), 'open_count': open_cases.count(), 'overdue': overdue,
        'awaiting_triage': cases.filter(status=Status.NEW).count(),
        'ftf_rate': _pct(ftf_known.filter(first_time_fix=True).count(), ftf_known.count()),
        'avg_hours': round(sum(durations) / len(durations), 1) if durations else None,
        'within_sla': _pct(sum(1 for c in resolved_with_sla if c.date_resolved <= c.sla_due), len(resolved_with_sla)),
        'ack_on_time': _pct(sum(1 for c in acked if c.date_acknowledged <= c.sla_acknowledge_due), acked.count()),
        'ai_accept': _pct(triaged.filter(ai_suggestion_accepted=True).count(), triaged.count()),
        'ai_triaged': triaged.count(),
        'duplicates': Case.objects.filter(status=Status.DUPLICATE).count(),
        'avg_satisfaction': round(sum(scores) / len(scores), 1) if scores else None,
        'feedback_count': len(scores),
    }


DUE_SOON = timedelta(hours=24)
REPLY_WAIT = timedelta(hours=24)
ATTENTION_SHOWN = 5  # rows shown in each group; the rest are counted


def _who(c):
    team = c.assigned_team.name if c.assigned_team else 'No team'
    return f'{team} · {c.assigned_officer.name if c.assigned_officer else "no officer"}'


def _needs_attention(now):
    """Cases a manager may need to act on now, grouped by what's wrong. A case can be in more than one
    group (an urgent job with no officer can also be overdue), because each group needs a different action.
    Each item is (case, note)."""
    open_cases = (Case.objects.filter(status__in=[Status.ASSIGNED, Status.IN_PROGRESS])
                  .select_related('assigned_team', 'assigned_officer'))
    overdue = [(c, f'Due {timesince(c.sla_due, now)} ago · {_who(c)}')
               for c in open_cases.filter(sla_due__lt=now).order_by('sla_due')]
    due_soon = [(c, f'Due in {timeuntil(c.sla_due, now)} · {_who(c)}')
                for c in open_cases.filter(sla_due__gte=now, sla_due__lt=now + DUE_SOON).order_by('sla_due')]
    no_officer = [(c, f'{c.assigned_team or "No team"} · reported {timesince(c.date_reported, now)} ago'
                      f'{" · health and safety risk" if c.hs_risk else ""}')
                  for c in open_cases.filter(assigned_officer__isnull=True)
                  .filter(Q(priority=Priority.URGENT) | Q(hs_risk=True)).order_by('sla_due')]

    # New reports waiting longer than the response target for the priority the AI suggested
    # (or the reporter chose), which is when the reporter should have heard from a person
    targets = dict(SLARule.objects.values_list('priority', 'acknowledge_hours'))
    slow_triage = []
    for c in Case.objects.filter(status=Status.NEW).order_by('date_reported'):
        hours = targets.get(c.ai_priority or c.reported_urgency)
        if hours is not None and now > c.date_reported + timedelta(hours=hours):
            slow_triage.append((c, f'Waiting {timesince(c.date_reported, now)} · target {hours} '
                                   f'hour{"s" if hours != 1 else ""}'))

    slow_reply = [(c, f'Fixed {timesince(c.date_resolved, now)} ago · {c.assigned_team or "No team"}')
                  for c in Case.objects.filter(status=Status.RESOLVED, date_resolved__lt=now - REPLY_WAIT)
                  .select_related('assigned_team').order_by('date_resolved')]
    unhappy = [(c, f'Rated {c.satisfaction}/5 · closed {timesince(c.date_closed, now)} ago'
                   f'{" · " + chr(8220) + c.satisfaction_comments[:80] + chr(8221) if c.satisfaction_comments else ""}')
               for c in _unhappy_reporters()]

    groups = [
        ('overdue', 'Overdue', 'Past the date we promised the reporter.', 'fa-clock', overdue),
        ('due-soon', 'Due in the next 24 hours', 'Check these are on track.', 'fa-hourglass-half', due_soon),
        ('no-officer', 'Urgent or unsafe, no officer', 'Nobody has been sent yet.', 'fa-user-slash', no_officer),
        ('slow-triage', 'Waiting too long for triage', "Past the response target, and the reporter hasn't heard from a person.",
         'fa-inbox', slow_triage),
        ('slow-reply', 'Fixed, no reply after a day', 'The outcome letter is still waiting for approval.',
         'fa-envelope', slow_reply),
        ('unhappy', 'Unhappy reporters', 'Rated the fix 2/5 or lower in the last four weeks.', 'fa-face-frown', unhappy),
    ]
    return [{'key': key, 'title': title, 'help': help_text, 'icon': icon, 'total': len(items),
             'items': items[:ATTENTION_SHOWN], 'more': max(len(items) - ATTENTION_SHOWN, 0),
             'case_ids': {c.pk for c, _ in items}}
            for key, title, help_text, icon, items in groups if items]


TREND_WEEKS = 8


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def _duration(hours):
    """Hours as people say them: "45 min", "6.5 hours", "3.2 days"."""
    if hours is None:
        return '-'
    if hours < 1:
        return f'{round(hours * 60)} min'
    if hours < 48:
        return f'{hours:.1f} hours'
    return f'{hours / 24:.1f} days'


def _trends(now):
    """Weekly reports in and fixes out for the last TREND_WEEKS weeks (Monday to Sunday, this week so far
    last), and the median time a case spends at each stage, for cases that moved on in the same period."""
    today = timezone.localtime(now).date()
    this_monday = today - timedelta(days=today.weekday())
    mondays = [this_monday - timedelta(weeks=n) for n in range(TREND_WEEKS - 1, -1, -1)]
    start = timezone.make_aware(timezone.datetime.combine(mondays[0], timezone.datetime.min.time()))

    def week_of(moment):
        day = timezone.localtime(moment).date()
        return (day - mondays[0]).days // 7

    reported = [0] * TREND_WEEKS
    resolved = [0] * TREND_WEEKS
    for moment in Case.objects.filter(date_reported__gte=start).values_list('date_reported', flat=True):
        reported[week_of(moment)] += 1
    for moment in (Case.objects.exclude(status=Status.DUPLICATE).filter(date_resolved__gte=start)
                   .values_list('date_resolved', flat=True)):
        resolved[week_of(moment)] += 1
    weeks = [{'label': 'This week' if i == TREND_WEEKS - 1 else f'{m.day} {m:%b}', 'start': m.isoformat(),
              'reported': r, 'resolved': f, 'partial': i == TREND_WEEKS - 1}
             for i, (m, r, f) in enumerate(zip(mondays, reported, resolved))]

    def hours(a, b):
        return (b - a).total_seconds() / 3600

    triage = [hours(r, a) for r, a in Case.objects.filter(date_acknowledged__gte=start)
              .values_list('date_reported', 'date_acknowledged')]
    fix = [hours(a, r) for a, r in Case.objects.filter(date_resolved__gte=start, date_acknowledged__isnull=False)
           .exclude(status=Status.DUPLICATE).values_list('date_acknowledged', 'date_resolved')]
    reply = [hours(r, c) for r, c in Case.objects.filter(status=Status.CLOSED, date_closed__gte=start,
                                                         date_resolved__isnull=False)
             .values_list('date_resolved', 'date_closed')]
    # The medians only count cases that have finished a stage, so say how many are still in each one
    in_stage = dict(Case.objects.order_by().values_list('status').annotate(n=Count('pk')))
    stages = [
        {'name': 'Waiting for triage', 'help': 'Reported to sent to a team', 'values': triage,
         'now': in_stage.get(Status.NEW, 0)},
        {'name': 'Being fixed', 'help': 'Sent to a team to fixed', 'values': fix,
         'now': in_stage.get(Status.ASSIGNED, 0) + in_stage.get(Status.IN_PROGRESS, 0)},
        {'name': 'Waiting for the reply', 'help': 'Fixed to outcome letter sent', 'values': reply,
         'now': in_stage.get(Status.RESOLVED, 0)},
    ]
    for st in stages:
        st['median'] = _median(st['values'])
        st['count'] = len(st['values'])
        st['text'] = _duration(st['median'])
        st['hours'] = round(st['median'], 1) if st['median'] is not None else None
        del st['values']
    longest = max((st for st in stages if st['median'] is not None), key=lambda st: st['median'], default=None)
    return {
        'weeks': weeks, 'stages': stages, 'longest_stage': longest,
        'reported_total': sum(reported), 'resolved_total': sum(resolved),
        'since': mondays[0],
    }


@role_required(Role.MANAGER)
def dashboard(request):
    now = timezone.now()
    cases = Case.objects.exclude(status=Status.DUPLICATE)
    teams = []
    for team in Team.objects.all():
        t_cases = cases.filter(assigned_team=team)
        t_res = t_cases.exclude(first_time_fix__isnull=True)
        teams.append({
            'name': team.name,
            'open': t_cases.filter(status__in=OPEN_STATUSES).count(),
            'overdue': t_cases.filter(status__in=OPEN_STATUSES, sla_due__lt=now).count(),
            'resolved': t_cases.filter(date_resolved__isnull=False).count(),
            'ftf': _pct(t_res.filter(first_time_fix=True).count(), t_res.count()),
        })
    max_open = max([t['open'] for t in teams] + [1])
    for t in teams:
        t['bar'] = round(100 * t['open'] / max_open)

    categories = (Category.objects.annotate(n=Count('case', filter=~Q(case__status=Status.DUPLICATE)))
                  .filter(n__gt=0).order_by('-n'))
    max_cat = max([c.n for c in categories] + [1])

    ctx = _dashboard_stats()
    attention = _needs_attention(now)
    trends = _trends(now)
    ctx.update({'teams': teams, 'categories': categories, 'max_cat': max_cat,
                'trends': trends,
                'trend_chart': {'weeks': trends['weeks'], 'stages': trends['stages']},
                'attention': attention, 'attention_total': len(set().union(*(g['case_ids'] for g in attention)))})
    return render(request, 'cases/dashboard.html', ctx)


@role_required(Role.MANAGER)
def people(request):
    """Managers decide who is a case handler, field officer or manager."""
    User = get_user_model()
    if request.method == 'POST':
        target = get_object_or_404(User, pk=request.POST.get('user_id'))
        form = RoleForm(request.POST)
        if target == request.user:
            messages.error(request, 'You cannot change your own role.')
        elif form.is_valid():
            role, team = form.cleaned_data['role'], form.cleaned_data['team']
            profile, _ = Profile.objects.get_or_create(user=target)
            profile.role = role
            profile.save()
            officer = getattr(target, 'officer', None)
            if role == Role.OFFICER:
                if officer:
                    officer.team = team
                    officer.save()
                else:
                    Officer.objects.create(user=target, team=team, name=display_name(target),
                                           contact_email=target.email or 'unknown@example.com')
            elif officer:
                # Keep the officer record for case history, just unlink the account
                officer.user = None
                officer.save()
            messages.success(request, f'{display_name(target)} is now: {Role(role).label}.')
        else:
            messages.error(request, 'Choose a team for a field officer.')
        return redirect('people')

    users = User.objects.select_related('profile', 'officer__team').order_by('first_name', 'username')
    rows = [{'user': u, 'role': get_role(u), 'team_id': getattr(getattr(u, 'officer', None), 'team_id', None)}
            for u in users]
    return render(request, 'cases/people.html', {'rows': rows, 'roles': Role.choices, 'teams': Team.objects.all()})
