"""Node and Proxmox permissions pages (PVE parity, phase 5).

Read-only: the recommended API token has Sys.Audit but none of the privileges
needed to change the node (Sys.Modify, Sys.PowerMgmt) or users and ACLs
(User.Modify, Permissions.Modify). Both areas are admin-only in the app.
"""

import logging
from datetime import datetime
from datetime import timezone as dt_timezone
from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from apps.backups.logic import fmt_bytes
from apps.proxmox.api import ProxmoxAPIError
from apps.proxmox.perms import token_can
from apps.wizard.models import ProxmoxConfig

logger = logging.getLogger(__name__)

NODE_TABS = [("services", "Services"), ("network", "Network"), ("dns", "DNS, hosts & time"),
             ("disks", "Disks"), ("updates", "Repositories & packages"), ("certificates", "Certificates"),
             ("hardware", "PCI devices")]
ACCESS_TABS = [("users", "Users"), ("groups", "Groups"), ("acl", "Permissions"), ("roles", "Roles"),
               ("pools", "Pools"), ("realms", "Realms")]
MAIN_PACKAGES = ("proxmox-ve", "pve-manager", "qemu-server", "pve-qemu-kvm", "lxc-pve", "pve-container",
                 "pve-kernel", "proxmox-kernel", "zfsutils-linux", "pve-firewall", "proxmox-backup-client",
                 "ceph", "corosync", "pve-ha-manager", "libpve-storage-perl", "novnc-pve")


def _ctx():
    config = ProxmoxConfig.objects.filter(is_configured=True).first()
    if config is None:
        raise Http404("Proxmox is not configured")
    return config.get_api_client(), config.default_node


def _ts(value):
    try:
        return timezone.localtime(datetime.fromtimestamp(int(value), tz=dt_timezone.utc))
    except (TypeError, ValueError, OSError):
        return None


def _safe(fn, default):
    try:
        return fn(), None
    except ProxmoxAPIError as exc:
        return default, exc.message


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def _services(api, node):
    rows = api._get(f"/nodes/{node}/services") or []
    for s in rows:
        s["ok"] = s.get("state") == "running" or s.get("unit-state") in ("disabled", "masked", "not-found")
        s["unit_state"] = s.get("unit-state", "")
        s["active_state"] = s.get("active-state", "")
    return sorted(rows, key=lambda s: s.get("name", ""))


def _network(api, node):
    rows = api._get(f"/nodes/{node}/network") or []
    order = {"bridge": 0, "bond": 1, "vlan": 2, "eth": 3}
    for i in rows:
        i["autostart_b"] = bool(i.get("autostart"))
        i["active_b"] = bool(i.get("active"))
        i["ports"] = i.get("bridge_ports") or i.get("slaves") or i.get("vlan-raw-device") or ""
    return sorted(rows, key=lambda i: (order.get(i.get("type"), 9), i.get("iface", "")))


def _dns(api, node):
    data = {"dns": api._get(f"/nodes/{node}/dns") or {}}
    t = api._get(f"/nodes/{node}/time") or {}
    data["time"] = {"timezone": t.get("timezone", ""), "now": _ts(t.get("time"))}
    hosts = api._get(f"/nodes/{node}/hosts") or {}
    data["hosts"] = hosts.get("data", "") if isinstance(hosts, dict) else ""
    return data


def _disks(api, node):
    disks = api._get(f"/nodes/{node}/disks/list") or []
    for d in disks:
        d["size_h"] = fmt_bytes(d.get("size"))
        w = d.get("wearout")
        d["wearout_h"] = f"{w}%" if isinstance(w, (int, float)) else (w or "—")
    lvm = api._get(f"/nodes/{node}/disks/lvm") or {}
    vgs = []
    for vg in (lvm.get("children") or []):
        vgs.append({"name": vg.get("name"), "size_h": fmt_bytes(vg.get("size")), "free_h": fmt_bytes(vg.get("free")),
                    "lvcount": vg.get("lvcount"), "pvs": [c.get("name") for c in vg.get("children") or []]})
    thin = api._get(f"/nodes/{node}/disks/lvmthin") or []
    for t in thin:
        size = int(t.get("lv_size") or 0)
        t["pct"] = round(100 * int(t.get("used") or 0) / size, 1) if size else 0
        msize = int(t.get("metadata_size") or 0)
        t["meta_pct"] = round(100 * int(t.get("metadata_used") or 0) / msize, 1) if msize else 0
        t["size_h"] = fmt_bytes(size)
    zfs = api._get(f"/nodes/{node}/disks/zfs") or []
    for z in zfs:
        z["size_h"], z["free_h"] = fmt_bytes(z.get("size")), fmt_bytes(z.get("free"))
    dirs = api._get(f"/nodes/{node}/disks/directory") or []
    return {"disks": disks, "vgs": vgs, "thin": thin, "zfs": zfs, "dirs": dirs}


def _updates(api, node):
    repos = api._get(f"/nodes/{node}/apt/repositories") or {}
    std = [r for r in repos.get("standard-repos", []) if r.get("status") is not None]
    files = []
    for f in repos.get("files", []):
        for r in f.get("repositories", []):
            files.append({
                "path": f.get("path", ""), "enabled": bool(r.get("Enabled")),
                "types": " ".join(r.get("Types", [])), "uris": " ".join(r.get("URIs", [])),
                "suites": " ".join(r.get("Suites", [])), "components": " ".join(r.get("Components", [])),
                "comment": r.get("Comment", "").strip(),
            })
    versions = api._get(f"/nodes/{node}/apt/versions") or []
    running_kernel = next((v.get("RunningKernel") for v in versions if v.get("RunningKernel")), "")
    main = [v for v in versions if v.get("Package", "").startswith(MAIN_PACKAGES)]
    sub = api._get(f"/nodes/{node}/subscription") or {}
    return {"std": std, "files": files, "errors": repos.get("errors", []), "versions": versions,
            "main": main, "running_kernel": running_kernel, "subscription": sub,
            "can_list_updates": token_can(f"/nodes/{node}", "Sys.Modify")}


def _certificates(api, node):
    certs = api._get(f"/nodes/{node}/certificates/info") or []
    now = timezone.now()
    for c in certs:
        c.pop("pem", None)
        c["not_after"] = _ts(c.get("notafter"))
        c["not_before"] = _ts(c.get("notbefore"))
        c["days_left"] = (c["not_after"] - now).days if c["not_after"] else None
        c["key"] = f"{c.get('public-key-type', '')} {c.get('public-key-bits', '')}".strip()
    return certs


def _hardware(api, node):
    rows = api._get(f"/nodes/{node}/hardware/pci") or []
    return sorted(rows, key=lambda p: p.get("id", ""))


NODE_LOADERS = {"services": _services, "network": _network, "dns": _dns, "disks": _disks,
                "updates": _updates, "certificates": _certificates, "hardware": _hardware}


@login_required
def node_page(request, tab="services"):
    if tab not in NODE_LOADERS:
        raise Http404
    api, node = _ctx()
    data, error = _safe(lambda: NODE_LOADERS[tab](api, node), None)
    return render(request, "node/node.html", {
        "tab": tab, "tabs": NODE_TABS, "data": data, "error": error, "node": node,
        "can_modify": token_can(f"/nodes/{node}", "Sys.Modify"), "help_slug": "node",
    })


@login_required
def node_smart(request):
    """HTMX partial: SMART report of one disk (only devices listed by PVE)."""
    api, node = _ctx()
    disk = request.GET.get("disk", "")
    try:
        known = {d.get("devpath") for d in api._get(f"/nodes/{node}/disks/list") or []}
        if disk not in known:
            raise Http404
        smart = api._get(f"/nodes/{node}/disks/smart", params={"disk": disk}, timeout=30) or {}
        error = None
    except ProxmoxAPIError as exc:
        smart, error = {}, exc.message
    attrs = smart.get("attributes") or []
    return render(request, "node/partials/smart.html", {
        "disk": disk, "smart": smart, "attrs": attrs, "text": smart.get("text", ""), "error": error,
    })


# ---------------------------------------------------------------------------
# Proxmox access control
# ---------------------------------------------------------------------------

def _users(api):
    users = api._get("/access/users", params={"full": 1}) or []
    for u in users:
        u["expire_d"] = _ts(u["expire"]) if u.get("expire") else None
        u["realm_type"] = u.get("realm-type", "")
        groups = u.get("groups") or []
        u["groups"] = [g for g in (groups.split(",") if isinstance(groups, str) else groups) if g]
        toks = u.get("tokens")
        u["token_names"] = [t.get("tokenid") for t in toks] if isinstance(toks, list) else None
    return sorted(users, key=lambda u: u.get("userid", ""))


def _acl(api):
    rows = api._get("/access/acl") or []
    return sorted(rows, key=lambda a: (a.get("path", ""), a.get("ugid", "")))


def _roles(api):
    rows = api._get("/access/roles") or []
    for r in rows:
        r["priv_list"] = sorted(p for p in (r.get("privs") or "").split(",") if p)
    return sorted(rows, key=lambda r: (not r.get("special"), r.get("roleid", "")))


def _pools(api):
    pools = api._get("/pools") or []
    for p in pools:
        try:
            p["members"] = (api._get(f"/pools/{quote(p['poolid'], safe='')}") or {}).get("members", [])
        except ProxmoxAPIError:
            p["members"] = []
    return pools


ACCESS_LOADERS = {
    "users": _users, "groups": lambda api: api._get("/access/groups") or [], "acl": _acl,
    "roles": _roles, "pools": _pools, "realms": lambda api: api._get("/access/domains") or [],
}


@login_required
def access_page(request, tab="users"):
    if tab not in ACCESS_LOADERS:
        raise Http404
    api, node = _ctx()
    data, error = _safe(lambda: ACCESS_LOADERS[tab](api), [])
    return render(request, "node/access.html", {
        "tab": tab, "tabs": ACCESS_TABS, "data": data, "error": error,
        "can_modify": token_can("/access", "User.Modify") or token_can("/access", "Permissions.Modify"),
        "help_slug": "pve-access",
    })
