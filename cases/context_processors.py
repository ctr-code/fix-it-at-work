from . import reporter_messages
from .alerts import unread_count
from .models import Role, get_role


def _label(n):
    return '99+' if n > 99 else str(n)


def role(request):
    """Make the signed-in user's role, and their unread counts for the navbar, available to every template:
    alerts (field officers) and new messages on reports they made (anyone can report)."""
    r = get_role(request.user)
    alerts = unread_count(request.user) if r == Role.OFFICER else 0
    messages = reporter_messages.unread_count(request.user)
    return {
        'user_role': r, 'user_role_label': Role(r).label if r else '',
        'unread_alerts': alerts, 'unread_alerts_label': _label(alerts),
        'unread_messages': messages, 'unread_messages_label': _label(messages),
        'unread_total': alerts + messages, 'unread_total_label': _label(alerts + messages),
    }
