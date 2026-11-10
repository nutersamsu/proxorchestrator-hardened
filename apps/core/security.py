"""Central security controls for ProxOrchestrator.

- AccessControlMiddleware: deny-by-default authentication and admin-only areas.
- Login throttling (per username and per client IP) backed by the Django cache.
- safe_next_url(): open-redirect-safe handling of ?next= parameters.
- user_is_admin(): single definition of "administrator" used everywhere.
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def user_is_admin(user):
    """Administrators are active staff users."""
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


# ---------------------------------------------------------------------------
# Redirect safety
# ---------------------------------------------------------------------------

def safe_next_url(request, candidate, default="/"):
    """Return candidate only if it is a same-site relative URL."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ) and candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return default


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

# Reachable without a session.
PUBLIC_PREFIXES = (
    "/login/",
    "/logout/",
    "/static/",
    "/help/",
    "/forgot-password/",
    "/reset-password/",
    "/mfa/verify/",
    "/mfa/recovery/email/",
    # Performs its own session check and answers 204/401/403 for nginx.
    "/internal/console-auth/",
    # Only the Microsoft (Entra ID) OAuth flow of allauth is exposed.
    "/accounts/microsoft/",
    "/accounts/3rdparty/login/",
    "/accounts/social/login/",
)

# allauth's own local-account views (login, signup, password reset, email...)
# bypass ProxOrchestrator's MFA and must never be reachable.
BLOCKED_ALLAUTH_PREFIX = "/accounts/"

# Paths that can change how ProxOrchestrator reaches Proxmox, manage users,
# read the local filesystem, or run arbitrary scripts as root on the host.
ADMIN_ONLY_PREFIXES = (
    "/admin/",
    "/settings/",
    "/users/",
    "/wizard/step/",
    "/wizard/local-browse/",
    "/wizard/local-mkdir/",
    "/lxc/new/community-scripts/",
    "/vm/new/community-scripts/",
)
# The wizard index only redirects to a step; keep it admin-only as well.
ADMIN_ONLY_EXACT = ("/wizard/",)


def path_is_public(path):
    return path.startswith(PUBLIC_PREFIXES)


def path_is_admin_only(path):
    return path in ADMIN_ONLY_EXACT or path.startswith(ADMIN_ONLY_PREFIXES)


class AccessControlMiddleware:
    """Deny by default: every non-public path needs an authenticated session,
    and administrative areas additionally need an admin (staff) account."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if path.startswith(BLOCKED_ALLAUTH_PREFIX) and not path_is_public(path):
            return redirect("/login/")

        # Django admin has its own login form that bypasses MFA.
        if path.startswith("/admin/login/"):
            return redirect("/login/?next=/admin/")

        if path_is_public(path):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            if request.headers.get("HX-Request"):
                resp = HttpResponseForbidden("Authentication required.")
                resp["HX-Redirect"] = "/login/"
                return resp
            return redirect(f"/login/?next={path}")

        if path_is_admin_only(path) and not user_is_admin(user):
            logger.warning("Denied non-admin user %s access to %s", user.username, path)
            return HttpResponseForbidden("Forbidden — administrator access required.")

        return self.get_response(request)


# ---------------------------------------------------------------------------
# Login throttling
# ---------------------------------------------------------------------------

LOGIN_MAX_FAILURES_PER_USER = getattr(settings, "LOGIN_MAX_FAILURES_PER_USER", 5)
LOGIN_MAX_FAILURES_PER_IP = getattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 20)
LOGIN_LOCKOUT_SECONDS = getattr(settings, "LOGIN_LOCKOUT_SECONDS", 15 * 60)


def client_ip(request):
    # nginx in front of gunicorn sets X-Real-IP; REMOTE_ADDR is the proxy.
    return (request.META.get("HTTP_X_REAL_IP")
            or request.META.get("REMOTE_ADDR")
            or "unknown")


def _key(kind, value):
    digest = hashlib.sha256(str(value).lower().encode()).hexdigest()[:32]
    return f"po:throttle:{kind}:{digest}"


def _incr(key):
    try:
        cache.add(key, 0, LOGIN_LOCKOUT_SECONDS)
        return cache.incr(key)
    except Exception:  # cache unavailable — fail closed for this attempt only
        logger.exception("Login throttle cache unavailable")
        return 10**6


def login_is_locked(request, username, scope="login"):
    try:
        by_user = cache.get(_key(f"{scope}:user", username), 0)
        by_ip = cache.get(_key(f"{scope}:ip", client_ip(request)), 0)
    except Exception:
        logger.exception("Login throttle cache unavailable")
        return True
    return by_user >= LOGIN_MAX_FAILURES_PER_USER or by_ip >= LOGIN_MAX_FAILURES_PER_IP


def register_login_failure(request, username, scope="login"):
    _incr(_key(f"{scope}:user", username))
    _incr(_key(f"{scope}:ip", client_ip(request)))


def reset_login_failures(request, username, scope="login"):
    try:
        cache.delete(_key(f"{scope}:user", username))
    except Exception:
        pass
