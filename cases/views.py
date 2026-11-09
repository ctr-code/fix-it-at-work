from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import ai
from .forms import LetterForm, ReportForm, TriageForm, VisitForm
from .models import (
    OPEN_STATUSES, PRIORITY_RANK, Case, Category, Communication, Officer, SiteVisit, Status, Team,
)


def home(request):
    return render(request, 'cases/home.html')


# ---------- 1. Report ----------

def report(request):
    if request.method == 'POST':
        form = ReportForm(request.POST, request.FILES)
        if form.is_valid():
            case = form.save()
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


def track(request):
    ref = request.GET.get('ref', '').strip().upper()
    if ref:
        if Case.objects.filter(reference=ref).exists():
            return redirect('track_case', ref=ref)
        messages.error(request, f'We could not find a report with reference {ref}.')
    return render(request, 'cases/track_search.html')


def track_case(request, ref):
    case = get_object_or_404(Case, reference=ref)
    sent = case.communications.filter(date_sent__isnull=False)
    return render(request, 'cases/track.html', {'case': case, 'sent': sent})


# ---------- 2. Triage and route (case handler) ----------

def triage_queue(request):
    new_cases = sorted(
        Case.objects.filter(status=Status.NEW).select_related('ai_category', 'ai_duplicate_candidate'),
        key=lambda c: (-PRIORITY_RANK.get(c.ai_priority, 0), c.date_reported),
    )
    awaiting_reply = Case.objects.filter(status=Status.RESOLVED).select_related('assigned_team')
    in_flight = Case.objects.filter(status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).select_related(
        'assigned_team', 'assigned_officer').order_by('sla_due')
    return render(request, 'cases/triage_queue.html', {
        'new_cases': new_cases, 'awaiting_reply': awaiting_reply, 'in_flight': in_flight,
    })


def triage_case(request, ref):
    case = get_object_or_404(Case, reference=ref)
    if case.status != Status.NEW:
        return redirect('case_detail', ref=ref)

    if request.method == 'POST':
        form = TriageForm(request.POST, case=case)
        if form.is_valid():
            d = form.cleaned_data
            case.triaged_by = d['triaged_by']
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
                    approved_by=d['triaged_by'], date_sent=timezone.now(),
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
                            f'{timezone.localtime(case.sla_due):%A %d %B}.'),
                approved_by=d['triaged_by'], date_sent=timezone.now(),
            )
            messages.success(request, f'{case.reference} sent to {case.assigned_team}.')
            return redirect('triage_queue')
    else:
        form = TriageForm(case=case, initial={
            'category': case.ai_category,
            'priority': case.ai_priority,
            'team': case.ai_category.default_team if case.ai_category else None,
        })
    officers_by_team = {}
    for o in Officer.objects.all():
        officers_by_team.setdefault(o.team_id, []).append(o.id)
    return render(request, 'cases/triage_case.html', {
        'case': case, 'form': form, 'officers_by_team': officers_by_team,
    })


def case_detail(request, ref):
    case = get_object_or_404(Case, reference=ref)
    return render(request, 'cases/case_detail.html', {'case': case})


# ---------- 3 & 4. Attend, investigate, record outcome (field officer) ----------

def officer_cases(request):
    if 'officer' in request.GET:
        request.session['officer_id'] = request.GET['officer']
    officer = Officer.objects.filter(pk=request.session.get('officer_id')).select_related('team').first()
    cases, team_unassigned = [], []
    if officer:
        cases = Case.objects.filter(
            assigned_officer=officer, status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).order_by('sla_due')
        team_unassigned = Case.objects.filter(
            assigned_team=officer.team, assigned_officer__isnull=True,
            status__in=[Status.ASSIGNED, Status.IN_PROGRESS]).order_by('sla_due')
    return render(request, 'cases/officer_cases.html', {
        'officer': officer, 'officers': Officer.objects.select_related('team'),
        'cases': cases, 'team_unassigned': team_unassigned,
    })


def officer_case(request, ref):
    case = get_object_or_404(Case, reference=ref)
    officer = Officer.objects.filter(pk=request.session.get('officer_id')).first()
    if not officer:
        messages.error(request, 'Choose which officer you are first.')
        return redirect('officer_cases')

    if request.method == 'POST' and 'take' in request.POST:
        case.assigned_officer = officer
        case.save()
        messages.success(request, f'{case.reference} is now assigned to you.')
        return redirect('officer_case', ref=ref)

    if request.method == 'POST':
        form = VisitForm(request.POST, request.FILES)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.case = case
            visit.officer = officer
            visit.ai_summary = ai.summarise_visit(visit.note, visit.fixed)
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

def outcome_letter(request, ref):
    case = get_object_or_404(Case, reference=ref)
    letter = case.communications.filter(kind=Communication.Kind.OUTCOME).first()
    if letter is None:
        letter = Communication.objects.create(
            case=case, kind=Communication.Kind.OUTCOME, language=case.preferred_language,
            draft_text=ai.draft_outcome_letter(case), ai_drafted=True,
        )
    if letter.date_sent:
        return redirect('case_detail', ref=ref)

    if request.method == 'POST':
        form = LetterForm(request.POST)
        if form.is_valid():
            letter.draft_text = form.cleaned_data['draft_text']
            letter.approved_by = form.cleaned_data['approved_by']
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


def dashboard(request):
    now = timezone.now()
    cases = Case.objects.exclude(status=Status.DUPLICATE)
    open_cases = cases.filter(status__in=OPEN_STATUSES)
    overdue = [c for c in open_cases.filter(sla_due__lt=now).select_related('assigned_team', 'assigned_officer')]

    resolved = cases.filter(date_resolved__isnull=False)
    ftf_known = resolved.exclude(first_time_fix__isnull=True)
    ftf_rate = _pct(ftf_known.filter(first_time_fix=True).count(), ftf_known.count())

    durations = [(c.date_resolved - c.date_reported).total_seconds() / 86400 for c in resolved]
    avg_days = round(sum(durations) / len(durations), 1) if durations else None

    resolved_with_sla = [c for c in resolved if c.sla_due]
    within_sla = _pct(sum(1 for c in resolved_with_sla if c.date_resolved <= c.sla_due), len(resolved_with_sla))

    acked = cases.filter(date_acknowledged__isnull=False, sla_acknowledge_due__isnull=False)
    ack_on_time = _pct(sum(1 for c in acked if c.date_acknowledged <= c.sla_acknowledge_due), acked.count())

    triaged = Case.objects.exclude(ai_suggestion_accepted__isnull=True)
    ai_accept = _pct(triaged.filter(ai_suggestion_accepted=True).count(), triaged.count())

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
    status_counts = {s.label: cases.filter(status=s.value).count() for s in Status if s != Status.DUPLICATE}

    return render(request, 'cases/dashboard.html', {
        'total': cases.count(), 'open_count': open_cases.count(), 'overdue': overdue,
        'awaiting_triage': cases.filter(status=Status.NEW).count(),
        'ftf_rate': ftf_rate, 'avg_days': avg_days, 'within_sla': within_sla,
        'ack_on_time': ack_on_time, 'ai_accept': ai_accept, 'ai_triaged': triaged.count(),
        'duplicates': Case.objects.filter(status=Status.DUPLICATE).count(),
        'teams': teams, 'categories': categories, 'max_cat': max_cat, 'status_counts': status_counts,
    })
