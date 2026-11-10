"""Allow-list for community script URLs executed on the Proxmox host."""

import re

_SCRIPT_URL_RE = re.compile(
    r"^https://raw\.githubusercontent\.com/community-scripts/ProxmoxVE/main/(ct|vm)/[A-Za-z0-9._-]+\.sh$"
)


def script_url_is_trusted(url):
    """Only scripts from the official community-scripts repository may run."""
    return bool(_SCRIPT_URL_RE.match(url or ""))
