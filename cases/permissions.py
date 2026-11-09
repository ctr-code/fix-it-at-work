"""Role checks used by the views."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import STAFF_ROLES, get_role


def role_required(*roles):
    """Only let signed-in users with one of these roles see the view."""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if get_role(request.user) not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def can_view_case(user, case):
    """Staff can see any case; reporters only their own; officers only their team's."""
    role = get_role(user)
    if role in STAFF_ROLES:
        return True
    if case.reporter_user_id == user.id:
        return True
    officer = getattr(user, 'officer', None)
    return role == 'officer' and officer is not None and case.assigned_team_id == officer.team_id
