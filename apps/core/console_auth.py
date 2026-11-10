"""Authorization for the nginx /vm-ws/ console proxy.

nginx injects the Proxmox API token into requests under /vm-ws/, so that
location must never be reachable without a check here. nginx calls this
view through ``auth_request`` for every console WebSocket handshake.

Access is granted only when:
  * the browser has a valid, fully logged-in Django session, and
  * the URI is exactly a VNC WebSocket endpoint, and
  * the same session opened the console page for that guest within the
    last CONSOLE_GRANT_SECONDS (a grant is recorded by ``grant_console``).
"""

import re
import time

from django.http import HttpResponse
from django.views.decorators.http import require_GET

CONSOLE_GRANT_SECONDS = 120
SESSION_KEY = "console_grants"

_URI_RE = re.compile(
    r"^/vm-ws/nodes/(?P<node>[A-Za-z0-9][A-Za-z0-9.\-]{0,62})/"
    r"(?P<kind>qemu|lxc)/(?P<vmid>[0-9]{1,9})/vncwebsocket\?"
    r"port=[0-9]{1,5}&vncticket=[A-Za-z0-9%:+/=._\-]+$"
)


def _grant_key(node, kind, vmid):
    return f"{node}/{kind}/{int(vmid)}"


def grant_console(request, node, kind, vmid):
    """Record that this session may open the console for node/kind/vmid."""
    now = time.time()
    grants = {
        k: exp for k, exp in request.session.get(SESSION_KEY, {}).items() if exp > now
    }
    grants[_grant_key(node, kind, vmid)] = now + CONSOLE_GRANT_SECONDS
    request.session[SESSION_KEY] = grants


@require_GET
def console_ws_auth(request):
    user = request.user
    if not user.is_authenticated or not user.is_active:
        return HttpResponse(status=401)
    profile = getattr(user, "profile", None)
    if profile is not None and getattr(profile, "must_change_password", False):
        return HttpResponse(status=403)

    uri = request.headers.get("X-Original-URI", "")
    match = _URI_RE.match(uri)
    if not match:
        return HttpResponse(status=403)

    grants = request.session.get(SESSION_KEY, {})
    expires = grants.get(_grant_key(match["node"], match["kind"], match["vmid"]), 0)
    if expires < time.time():
        return HttpResponse(status=403)
    return HttpResponse(status=204)
