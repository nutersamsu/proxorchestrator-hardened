"""allauth adapters.

ProxOrchestrator uses allauth ONLY for Microsoft Entra ID sign-in. Local
accounts are created by administrators, so allauth's own signup is closed.

Entra ID rules (fail closed):
  * a specific tenant must be configured — "common", "organizations" and
    "consumers" would let any Microsoft account in the world sign in;
  * a Microsoft identity is never linked to an existing local or LDAP
    account just because the e-mail matches (the ``mail`` attribute is
    user-controlled in many tenants, so that would allow account takeover
    and would also switch the account to "entra", skipping local MFA).
"""

import logging
import re

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger(__name__)

User = get_user_model()

_MULTI_TENANT = {"", "common", "organizations", "consumers"}
_TENANT_RE = re.compile(
    r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)$"
)


def tenant_is_valid(tenant_id):
    tenant_id = (tenant_id or "").strip()
    return tenant_id.lower() not in _MULTI_TENANT and bool(_TENANT_RE.match(tenant_id))


def _entra_config():
    from apps.authconfig.models import EntraIDConfig
    cfg = EntraIDConfig.objects.first()
    if cfg and cfg.is_enabled and tenant_is_valid(cfg.tenant_id):
        return cfg
    return None


def _deny(request, message):
    messages.error(request, message)
    raise ImmediateHttpResponse(redirect("/login/"))


class ClosedAccountAdapter(DefaultAccountAdapter):
    """No self-service local signup."""

    def is_open_for_signup(self, request):
        return False


class AutoSignupSocialAdapter(DefaultSocialAccountAdapter):

    def is_open_for_signup(self, request, sociallogin):
        return sociallogin.account.provider == "microsoft" and _entra_config() is not None

    def is_auto_signup_allowed(self, request, sociallogin):
        return self.is_open_for_signup(request, sociallogin)

    def pre_social_login(self, request, sociallogin):
        if sociallogin.account.provider != "microsoft" or _entra_config() is None:
            _deny(request, "Microsoft sign-in is not enabled.")

        cfg = _entra_config()
        extra = sociallogin.account.extra_data or {}
        upn = (extra.get("userPrincipalName") or "").lower()
        email = (extra.get("mail") or upn or "")

        allowed = [d.strip().lower().lstrip("@")
                   for d in (cfg.allowed_domains or "").replace(";", ",").split(",") if d.strip()]
        if allowed:
            domain = upn.rsplit("@", 1)[-1] if "@" in upn else ""
            if domain not in allowed:
                logger.warning("Entra sign-in refused for %s: domain not allowed", upn or "?")
                _deny(request, "Your Microsoft account is not authorized to access ProxOrchestrator.")

        if sociallogin.is_existing:
            return

        if not email:
            return

        matches = list(User.objects.filter(email__iexact=email)[:2])
        if not matches:
            return
        if len(matches) > 1:
            _deny(request, "More than one account uses this e-mail address. Contact your administrator.")

        user = matches[0]
        profile = getattr(user, "profile", None)
        if profile is not None and profile.auth_source == "entra":
            # Re-link an account that was created through Entra ID before.
            sociallogin.connect(request, user)
            return

        logger.warning(
            "Refused to link Microsoft identity %s to existing %s account %s",
            sociallogin.account.uid, getattr(profile, "auth_source", "local"), user.username,
        )
        _deny(request, "An account with this e-mail already exists. Ask an administrator "
                       "to link it; Microsoft sign-in cannot take over local accounts.")

    def populate_user(self, request, sociallogin, data):
        """Generate a username from the Microsoft account data."""
        user = super().populate_user(request, sociallogin, data)

        if not user.username:
            email = data.get("email", "") or ""
            base = email.split("@")[0] if email else f"entra_{sociallogin.account.uid[:8]}"
            username, n = base, 1
            while User.objects.filter(username__iexact=username).exists():
                n += 1
                username = f"{base}{n}"
            user.username = username

        # New Entra users never start as administrators unless the admin
        # group check in apps.authconfig.apps grants it.
        user.is_staff = getattr(user, "is_staff", False) and bool(user.pk)
        user.is_superuser = getattr(user, "is_superuser", False) and bool(user.pk)
        return user
