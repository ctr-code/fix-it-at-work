from .models import Role, get_role


def role(request):
    """Make the signed-in user's role available to every template."""
    r = get_role(request.user)
    return {'user_role': r, 'user_role_label': Role(r).label if r else ''}
