"""
Role-style access using Django auth Group + Permission.

Assign users to groups (e.g. Operations, Finance) in Django admin, or rely on
migration `0019_rbac_default_groups` which grants all custom permissions to staff.
"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def _full_perm(codename: str) -> str:
    return f"NelsaApp.{codename}"


def user_has_perm(user, codename: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(_full_perm(codename))


def user_has_any_perm(user, *codenames: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return any(user.has_perm(_full_perm(c)) for c in codenames)


def require_perm(codename: str):
    """Staff-only: must have NelsaApp.<codename> or superuser."""

    def decorator(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(reverse("Login"))
            if request.user.is_superuser:
                return view(request, *args, **kwargs)
            if not request.user.is_staff:
                messages.error(request, "Staff access required.")
                return redirect("index")
            if user_has_perm(request.user, codename):
                return view(request, *args, **kwargs)
            messages.error(request, "You do not have permission to perform this action.")
            return redirect("index")

        return _wrapped

    return decorator


def require_any_perm(*codenames: str):
    def decorator(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(reverse("Login"))
            if request.user.is_superuser:
                return view(request, *args, **kwargs)
            if not request.user.is_staff:
                messages.error(request, "Staff access required.")
                return redirect("index")
            if user_has_any_perm(request.user, *codenames):
                return view(request, *args, **kwargs)
            messages.error(request, "You do not have permission to perform this action.")
            return redirect("index")

        return _wrapped

    return decorator


def can_access_admin_portal(user) -> bool:
    """Any staff ops area (dashboard, bookings, routes, finance, etc.)."""
    return user_has_any_perm(
        user,
        "access_admin_bookings",
        "manage_routes_schedules",
        "view_paymentwebhooks",
        "view_adminauditlog",
        "manage_sms_ops",
        "manage_staff_users",
        "manage_refunds_rebooks",
    )


# Dashboard: any ops role (matches Finance + Operations groups).
require_admin_portal = require_any_perm(
    "access_admin_bookings",
    "manage_routes_schedules",
    "view_paymentwebhooks",
    "view_adminauditlog",
    "manage_sms_ops",
    "manage_staff_users",
    "manage_refunds_rebooks",
)
