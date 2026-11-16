"""Effective Proxmox privileges of the configured API token.

The UI only offers actions the token can actually perform. ``GET
/access/permissions`` returns, for every ACL path the token has a role on
(and its parents), the privileges that apply there. A path that is not listed
inherits from its closest listed ancestor, the same rule Proxmox uses for
propagated ACLs.

The result is cached for a few minutes; when the token is given more rights
the new buttons appear without a restart.
"""

import logging
import re

from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = "po:pve:token-perms"
CACHE_SECONDS = 300

_PATH_RE = re.compile(r"^/[A-Za-z0-9._/-]*$")


def _load(config):
    perms = cache.get(CACHE_KEY)
    if perms is not None:
        return perms
    try:
        perms = config.get_api_client().get_permissions()
    except Exception as exc:  # unreachable Proxmox: offer nothing extra
        logger.warning("Could not read token permissions: %s", exc)
        return {}
    cache.set(CACHE_KEY, perms, CACHE_SECONDS)
    return perms


def clear_cache():
    cache.delete(CACHE_KEY)


def privileges_at(perms, path):
    """Privileges that apply at ``path`` (nearest listed ancestor wins)."""
    if not path or not _PATH_RE.match(path):
        return set()
    path = path.rstrip("/") or "/"
    while True:
        entry = perms.get(path)
        if entry is not None:
            return {k for k, v in entry.items() if v}
        if path == "/":
            return set()
        path = path.rsplit("/", 1)[0] or "/"


def token_can(path, privilege, config=None, perms=None):
    """True when the API token holds ``privilege`` on ``path``."""
    if perms is None:
        if config is None:
            from apps.wizard.models import ProxmoxConfig
            config = ProxmoxConfig.objects.filter(is_configured=True).first()
            if config is None:
                return False
        perms = _load(config)
    return privilege in privileges_at(perms, path)
