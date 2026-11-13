from . import reporter_messages
from .alerts import unread_count
from .models import Case, Role, Status, get_role


def _label(n):
    return '99+' if n > 99 else str(n)


def waiting_for_handlers():
    """Cases where a case handler's action is the next step: new reports to triage, and fixed ones that need
    the outcome letter sent. These are the "Needs triage" and "Fixed - reply needed" tabs of the Case queue.
    (Unhappy reporters stay listed for weeks whatever is done, so they aren't counted.)"""
    return Case.objects.filter(status__in=[Status.NEW, Status.RESOLVED]).count()


def role(request):
    """Make the signed-in user's role, and their counts for the navbar, available to every template:
    unread alerts (field officers), cases waiting (case handlers and managers) and new messages on reports
    they made (anyone can report)."""
    r = get_role(request.user)
    alerts = unread_count(request.user) if r == Role.OFFICER else 0
    queue = waiting_for_handlers() if r in (Role.HANDLER, Role.MANAGER) else 0
    messages = reporter_messages.unread_count(request.user)
    total = alerts + queue + messages
    return {
        'user_role': r, 'user_role_label': Role(r).label if r else '',
        'unread_alerts': alerts, 'unread_alerts_label': _label(alerts),
        'queue_waiting': queue, 'queue_waiting_label': _label(queue),
        'unread_messages': messages, 'unread_messages_label': _label(messages),
        'unread_total': total, 'unread_total_label': _label(total),
    }
