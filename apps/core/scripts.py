"""Allow-list for community script URLs executed on the Proxmox host."""

import re

_SCRIPT_URL_RE = re.compile(
    r"^https://raw\.githubusercontent\.com/community-scripts/ProxmoxVE/main/(ct|vm)/[A-Za-z0-9._-]+\.sh$"
)


# The community-scripts core no longer honours var_diagnostics; it asks once
# per host with a whiptail dialog whose default answer is "Yes" and stores the
# answer in /usr/local/community-scripts/diagnostics. Opt out up front unless
# the administrator already made a choice on that host.
DIAGNOSTICS_OPT_OUT = (
    "_cs_d=/usr/local/community-scripts; "
    '[ -f "$_cs_d/diagnostics" ] || '
    '{ mkdir -p "$_cs_d" && printf "DIAGNOSTICS=no\\n" > "$_cs_d/diagnostics"; }; '
)


def fetch_and_run(quoted_url):
    """Shell snippet that downloads a script and runs it, failing loudly.

    The original `bash -c "$(curl -fsSL URL)"` exits 0 when the download
    fails (404, network error): bash runs an empty string and the job was
    reported as successful although nothing happened.
    """
    return (
        f"_cs_script=\"$(curl -fsSL {quoted_url})\" && [ -n \"$_cs_script\" ] "
        f"|| {{ echo \"ProxOrchestrator: could not download {quoted_url}\" >&2; exit 97; }}; "
        'bash -c "$_cs_script"'
    )


def script_url_is_trusted(url):
    """Only scripts from the official community-scripts repository may run."""
    return bool(_SCRIPT_URL_RE.match(url or ""))
