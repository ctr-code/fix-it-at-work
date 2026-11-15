"""
Alerts to the team (and officer) a case has been sent to, and the early warning when an urgent or unsafe
report arrives.

Every alert is emailed and also saved as an Alert, so the case page shows who was told what and when,
even when email only goes to the server window (the default, see EMAIL_BACKEND in settings).
"""
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import Alert


def _recipients(case, also=None):
    """The team's inbox, the assigned officer, and anyone else who needs to know, without repeats."""
    emails = [case.assigned_team.contact_email if case.assigned_team else '',
              case.assigned_officer.contact_email if case.assigned_officer else '',
              *(also or [])]
    seen = []
    for email in emails:
        if email and email.lower() not in (e.lower() for e in seen):
            seen.append(email)
    return seen


def _body(case, intro, link):
    due = f'{timezone.localtime(case.sla_due):%H:%M on %A %d %B}' if case.sla_due else 'not set'
    where = case.building + (f', {case.location_detail}' if case.location_detail else '')
    lines = [
        intro,
        '',
        f'Reference: {case.reference}',
        f'Issue: {case.title}',
        f'Priority: {case.get_priority_display()}',
        f'Resolve by: {due}',
        f'Where: {where}',
        f'Officer: {case.assigned_officer.name if case.assigned_officer else "Not yet assigned - anyone in the team can take it"}',
    ]
    if case.hs_risk:
        lines.append('HEALTH AND SAFETY RISK - make the area safe first.')
    summary = case.ai_summary or case.description
    if summary:
        lines += ['', f'Summary: {summary}']
    if link:
        lines += ['', f'Open the job: {link}']
    return '\n'.join(lines)


def subject_for(case):
    """Priority first, so urgent jobs stand out in an inbox list."""
    return (f'[{case.get_priority_display()}] {case.reference} {case.title}'
            f'{" - health and safety risk" if case.hs_risk else ""}')


def routed_intro(case):
    who = f'{case.assigned_officer.name}, you have' if case.assigned_officer else f'{case.assigned_team} has'
    return f'{who} a new {case.get_priority_display().lower()} priority job.'


def changed_intro(case, changes, old_officer=None):
    intro = 'This job has been changed:\n' + '\n'.join(f'- {line}' for line in changes)
    if old_officer and old_officer != case.assigned_officer:
        intro += f'\n{old_officer.name} no longer needs to attend.'
    return intro


def send_case_alert(case, kind, intro, request=None, also=None, also_officers=()):
    """Email the case's team and officer (plus `also`) and record the alert. Never raises: a failed email
    must not stop a case being routed, so the failure is recorded on the alert instead."""
    to = _recipients(case, also)
    if not to:
        return None
    link = request.build_absolute_uri(reverse('officer_case', args=[case.reference])) if request else ''
    subject = subject_for(case)
    body = _body(case, intro, link)
    alert = Alert(case=case, kind=kind, recipients=', '.join(to), subject=subject, body=body)
    try:
        send_mail(subject, body, None, to)
        alert.delivered = True
    except Exception as exc:  # noqa: BLE001 - any mail failure is recorded, not shown as a crash
        alert.error = str(exc)[:200]
    alert.team = case.assigned_team
    alert.save()
    alert.officers.set([o for o in (case.assigned_officer, *also_officers) if o])
    return alert


def alert_routed(case, request=None):
    """After triage: tell the team (and officer, if one was chosen) they have a new job."""
    return send_case_alert(case, Alert.Kind.ROUTED, routed_intro(case), request)


def alert_changed(case, changes, old_officer=None, request=None):
    """After a handler changes a triaged case: tell the team and officer now responsible, and an officer
    who has been taken off it."""
    also, also_officers = [], []
    if old_officer and old_officer != case.assigned_officer:
        also_officers.append(old_officer)
        if old_officer.contact_email:
            also.append(old_officer.contact_email)
    return send_case_alert(case, Alert.Kind.CHANGED, changed_intro(case, changes, old_officer), request, also,
                           also_officers)


# ---------- Early warning: an urgent or unsafe report has just arrived ----------

def needs_early_warning(case):
    """Urgent by the reporter's own choice or the AI's, or "This could hurt someone" ticked."""
    return case.hs_risk or 'urgent' in (case.reported_urgency, case.ai_priority)


def _handler_emails():
    """Everyone who triages: case handlers, or the managers if there are no handlers."""
    from django.contrib.auth import get_user_model
    from .models import Role
    users = get_user_model().objects.filter(is_active=True).exclude(email='')
    emails = list(users.filter(profile__role=Role.HANDLER).values_list('email', flat=True))
    return emails or list(users.filter(profile__role=Role.MANAGER).values_list('email', flat=True))


def _why_urgent(case):
    reasons = []
    if case.reported_urgency == 'urgent':
        reasons.append('the reporter said it is urgent')
    if case.ai_priority == 'urgent':
        reasons.append('the AI suggests urgent')
    if case.hs_risk:
        reasons.append('the reporter ticked "This could hurt someone"')
    return ', '.join(reasons[:-1]) + (' and ' if len(reasons) > 1 else '') + reasons[-1]


def _early_body(case, intro, link):
    where = case.building + (f', {case.location_detail}' if case.location_detail else '')
    team = case.ai_category.default_team if case.ai_category else None
    lines = [
        intro,
        '',
        f'Reference: {case.reference}',
        f'Issue: {case.title}',
        f'Why it is urgent: {_why_urgent(case)}',
        f'Reported: {timezone.localtime(case.date_reported):%H:%M on %A %d %B}',
        f'Where: {where}',
        f'AI suggests: {team.name if team else "no team yet"}',
    ]
    if case.hs_risk:
        lines.append('HEALTH AND SAFETY RISK - the area may need making safe first.')
    summary = case.ai_summary or case.description
    if summary:
        lines += ['', f'Summary: {summary}']
    if link:
        lines += ['', f'Triage it now: {link}']
    return '\n'.join(lines)


def _send(case, kind, to, subject, body, team=None):
    alert = Alert(case=case, kind=kind, recipients=', '.join(to), subject=subject, body=body, team=team)
    try:
        send_mail(subject, body, None, to)
        alert.delivered = True
    except Exception as exc:  # noqa: BLE001 - recorded on the alert, never stops the report
        alert.error = str(exc)[:200]
    alert.save()
    return alert


def early_warning(case, request=None):
    """As soon as an urgent or unsafe report arrives: tell the case handlers so it's triaged first, and give
    the team the AI suggested a heads-up so they can get ready. Nothing is routed: a handler still decides
    which team gets it, and that team then gets the usual "New job" alert. Returns the alerts sent."""
    if not needs_early_warning(case):
        return []
    sent = []
    flag = ' - health and safety risk' if case.hs_risk else ''
    handlers = _handler_emails()
    if handlers:
        link = request.build_absolute_uri(reverse('triage_case', args=[case.reference])) if request else ''
        intro = 'An urgent report has just arrived and is waiting for triage. Please check it first.'
        sent.append(_send(case, Alert.Kind.URGENT, handlers,
                          f'[Urgent - waiting for triage] {case.reference} {case.title}{flag}',
                          _early_body(case, intro, link)))
    team = case.ai_category.default_team if case.ai_category else None
    if team and team.contact_email:
        intro = (f'Heads-up for {team.name}: an urgent report that will probably come to you is waiting for a '
                 'case handler. Nothing to do yet - you will get a "New job" alert if it is sent to your team.')
        sent.append(_send(case, Alert.Kind.HEADS_UP, [team.contact_email],
                          f'[Heads-up] {case.reference} {case.title}{flag}',
                          _early_body(case, intro, ''), team=team))
    return sent


def unread_count(user):
    """How many alerts this person hasn't read yet, for the badge in the navbar. Only officers get alerts."""
    officer = getattr(user, 'officer', None) if user.is_authenticated else None
    if officer is None:
        return 0
    return Alert.for_officer(officer).exclude(reads__user=user).count()
