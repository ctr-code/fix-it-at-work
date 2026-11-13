"""The event history on the case page: everything that happened to a case, oldest first.

Built from the records the app already keeps: the case itself (reported, triaged, closed), the reporter's
extra details, changes made by handlers (and officers taking a job), team alerts (to say who was notified),
site visits and messages to the reporter.
"""
import re
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from .models import Alert, Status

# A change and the alert it sends are saved in the same request, so the alert follows within moments
ALERT_WINDOW = timedelta(minutes=1)


@dataclass
class Event:
    when: object  # a datetime, or None for an unsent draft (shown last)
    kind: str     # reported, details, triaged, assigned, changed, visit, message, draft, closed
    title: str
    by: str = ''
    lines: list = field(default_factory=list)
    note: str = ''        # who was notified, if anyone
    note_failed: bool = False
    item: object = None   # the visit, message or update, for its own details
    day: int = None       # calendar days since the case was reported (day 0 is the day it came in)


def _notified(alert):
    """'Serena and the Facilities Helpdesk team were notified by email.' (or that the email failed)."""
    names = [o.name for o in alert.officers.all()]
    if alert.team:
        team = str(alert.team)
        names.append(f'the {team}' if team.lower().endswith(' team') else f'the {team} team')
    if not names:
        names = [alert.recipients]
    who = names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
    if alert.delivered:
        return f'{who[0].upper()}{who[1:]} {"were" if len(names) > 1 else "was"} notified by email.', False
    return f'The email to {who} could not be sent.', True


def _change_title(lines):
    titles = []
    for line in lines:
        name, _, values = line.partition(': ')
        new = values.split(' → ')[-1]
        if name == 'Priority':
            titles.append('Reprioritised')
        elif name == 'Team':
            titles.append(f'Moved to {new}')
        elif name == 'Category':
            titles.append('Recategorised')
        elif name == 'Officer':
            titles.append('Officer removed' if new == 'Unassigned' else f'Assigned to {new}')
    return '; '.join(titles) or 'Changed'


def case_history(case):
    events = [Event(case.date_reported, 'reported', f'Reported by {case.reporter_name}')]

    for u in case.updates.all():
        events.append(Event(u.created_at, 'details', 'Reporter added more details', item=u))

    alerts = list(case.alerts.order_by('sent_at', 'pk').prefetch_related('officers').select_related('team'))
    routed = next((a for a in alerts if a.kind == Alert.Kind.ROUTED), None)
    if case.date_acknowledged:
        if case.status == Status.DUPLICATE and case.duplicate_of:
            events.append(Event(case.date_acknowledged, 'triaged',
                                f'Merged as a duplicate of {case.duplicate_of.reference}', by=case.triaged_by))
        else:
            priority = re.match(r'\[(\w+)\]', routed.subject) if routed else None
            lines = [f'{priority.group(1)} priority'] if priority else []
            events.append(Event(case.date_acknowledged, 'triaged', 'Triaged', by=case.triaged_by, lines=lines))
    if routed:
        officers = [o.name for o in routed.officers.all()]
        title = f'Assigned to {officers[0]}' if officers else 'Sent to the team (no officer chosen yet)'
        note, failed = _notified(routed)
        events.append(Event(routed.sent_at, 'assigned', title,
                            lines=[f'Team: {routed.team}'] if routed.team else [], note=note, note_failed=failed))

    changed_alerts = [a for a in alerts if a.kind == Alert.Kind.CHANGED]
    for ch in sorted(case.changes.all(), key=lambda c: (c.changed_at, c.pk)):
        lines = ch.lines()
        event = Event(ch.changed_at, 'changed', _change_title(lines), by=ch.changed_by, lines=lines)
        if ch.reason:
            event.lines = lines + [f'Reason: {ch.reason}']
        alert = next((a for a in changed_alerts if ch.changed_at <= a.sent_at <= ch.changed_at + ALERT_WINDOW), None)
        if alert:
            changed_alerts.remove(alert)
            event.note, event.note_failed = _notified(alert)
        events.append(event)

    for v in case.visits.all():
        events.append(Event(v.visited_at, 'visit', f'Site visit: {"fixed" if v.fixed else "follow-up needed"}',
                            by=v.officer.name, item=v))

    for c in case.communications.all():
        if c.date_sent:
            events.append(Event(c.date_sent, 'message', f'Message to reporter: {c.get_kind_display()}',
                                by=c.approved_by, item=c))
        else:
            events.append(Event(None, 'draft', f'{c.get_kind_display()} drafted, not yet sent', item=c))

    if case.status == Status.CLOSED and case.date_closed:
        events.append(Event(case.date_closed, 'closed', 'Case closed'))

    # Oldest first; things recorded at the same moment stay in the order added above. Drafts go last.
    events.sort(key=lambda e: (e.when is None, e.when or 0))
    start = timezone.localdate(case.date_reported)
    for e in events:
        if e.when:
            e.day = (timezone.localdate(e.when) - start).days
    return events
