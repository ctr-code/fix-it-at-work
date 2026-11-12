from .alerts import unread_count
from .models import Role, get_role


def role(request):
    """Make the signed-in user's role, and an officer's unread alert count, available to every template."""
    r = get_role(request.user)
    unread = unread_count(request.user) if r == Role.OFFICER else 0
    return {'user_role': r, 'user_role_label': Role(r).label if r else '',
            'unread_alerts': unread, 'unread_alerts_label': '99+' if unread > 99 else str(unread)}
