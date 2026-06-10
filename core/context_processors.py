"""Context processors for the core app."""

from accounts.models import UserRole


def user_roles(request):
    """Add user role flags to the template context."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {}

    user = request.user
    if user.is_superuser:
        role_set = {"cto"}
    else:
        role_set = set(
            UserRole.objects.filter(user=user, is_active=True).values_list(
                "role", flat=True
            )
        )

    admin_roles = {"cto", "ses_manager", "vp_player_agents", "president"}

    return {
        "user_is_admin": bool(role_set & admin_roles),
        "user_is_cto": "cto" in role_set,
        "user_is_coach": bool(role_set & {"head_coach", "assistant_coach"}),
        "user_is_front_desk": "front_desk" in role_set,
        "lms_power_user": user.is_superuser or user.lms_power_user,
    }
