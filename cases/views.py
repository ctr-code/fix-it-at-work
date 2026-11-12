from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import ai
from .forms import FeedbackForm, LetterForm, ReportForm, RoleForm, TriageForm, VisitForm
from .models import (
    OPEN_STATUSES, PRIORITY_RANK, UNHAPPY_FOLLOW_UP, UNHAPPY_SCORE, Case, Category, Communication, Officer, Profile, ReportPhoto, Role, Status,
    Priority, Team, get_role,
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
            Communication.objects.create(
                case=case, kind=Communication.Kind.RECEIPT, language=case.preferred_language,
                draft_text=ai.receipt_text(case), approved_by='Automatic', date_sent=timezone.now(),
            )
            messages.success(request, f'Thank you - your report has been received. Your reference is {case.reference}.')
            return redirect('track_case', ref=case.reference)
    else:
        form = ReportForm()
    buildings = Case.objects.values_list('building', flat=True).distinct()
    return render(request, 'cases/report.html', {'form': form, 'buildings': buildings})


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
    sent = case.communications.filter(date_sent__isnull=False)
    return render(request, 'cases/track.html', {'case': case, 'sent': sent, 'feedback_form': feedback_form})


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
    return render(request, 'cases/triage_queue.html', {
        'new_cases': new_cases, 'awaiting_reply': awaiting_reply, 'in_flight': in_flight,
        'unhappy': _unhappy_reporters(),
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
                Communication.objects.create(
                    case=case, kind=Communication.Kind.ACKNOWLEDGEMENT, language=case.preferred_language,
                    draft_text=(f'Thanks for your report. Someone has already reported this issue, so we have '
                                f'linked your report to {case.duplicate_of.reference}. You can track progress there.'),
                    approved_by=approver, date_sent=timezone.now(),
                )
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
            Communication.objects.create(
                case=case, kind=Communication.Kind.ACKNOWLEDGEMENT, language=case.preferred_language,
                draft_text=(f'Your report {case.reference} has been passed to our {case.assigned_team} team '
                            f'as {case.get_priority_display().lower()} priority. We aim to resolve it by '
                            f'{timezone.localtime(case.sla_due):%H:%M on %A %d %B}.'),
                approved_by=approver, date_sent=timezone.now(),
            )
            messages.success(request, f'{case.reference} sent to {case.assigned_team}.')
            return redirect('triage_queue')
    else:
        form = TriageForm(case=case, initial={
            'team': case.ai_category.default_team if case.ai_category else None,
            'category': case.ai_category,
            'priority': case.ai_priority,
        })
    # Lets the page narrow the category and officer lists to the chosen team
    by_team = {
        'category': {t: [] for t in Team.objects.values_list('id', flat=True)},
        'officer': {t: [] for t in Team.objects.values_list('id', flat=True)},
    }
    for cat_id, team_id in Category.objects.values_list('id', 'default_team_id'):
        by_team['category'][team_id].append(cat_id)
    for officer_id, team_id in Officer.objects.values_list('id', 'team_id'):
        by_team['officer'][team_id].append(officer_id)
    return render(request, 'cases/triage_case.html', {'case': case, 'form': form, 'by_team': by_team})


@role_required(*HANDLERS)
def case_detail(request, ref):
    case = get_object_or_404(Case, reference=ref)
    return render(request, 'cases/case_detail.html', {'case': case})


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
            return redirect('officer_cases')
    else:
        form = VisitForm()
    return render(request, 'cases/officer_case.html', {'case': case, 'form': form, 'officer': officer})


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
    ctx.update({'teams': teams, 'categories': categories, 'max_cat': max_cat})
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
