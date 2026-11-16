"""Firewall pages (PVE parity, phase 4).

A "scope key" in the URL selects the firewall level:
  dc | node | vm-<vmid> | ct-<vmid> | group-<name>
"""

import logging
import re
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.firewall import fw
from apps.proxmox.api import ProxmoxAPIError
from apps.proxmox.perms import token_can
from apps.wizard.models import ProxmoxConfig

logger = logging.getLogger(__name__)

SCOPE_KEY_RE = re.compile(r"^(dc|node|vm-\d{3,9}|ct-\d{3,9}|group-[A-Za-z][A-Za-z0-9_-]{1,17})$")
DIGEST_RE = re.compile(r"^[0-9a-f]{40}$")


def _ctx():
    config = ProxmoxConfig.objects.filter(is_configured=True).first()
    if config is None:
        raise Http404("Proxmox is not configured")
    return config.get_api_client(), config.default_node


def _scope(key, node):
    if not SCOPE_KEY_RE.match(key or ""):
        raise Http404("Unknown firewall scope")
    if key == "dc":
        return fw.Scope("cluster")
    if key == "node":
        return fw.Scope("node", node=node)
    if key.startswith("vm-"):
        return fw.Scope("qemu", node=node, vmid=int(key[3:]))
    if key.startswith("ct-"):
        return fw.Scope("lxc", node=node, vmid=int(key[3:]))
    return fw.Scope("group", group=key[6:])


def _editable(scope):
    return token_can(scope.acl_path, scope.edit_privilege)


def _back(request, key):
    nxt = request.POST.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect("firewall_index")


def _macros(api):
    try:
        return {m["macro"]: m.get("descr", "") for m in api._get("/cluster/firewall/macros") or []}
    except ProxmoxAPIError:
        return {}


def _groups(api):
    try:
        return [g["group"] for g in api._get("/cluster/firewall/groups") or []]
    except ProxmoxAPIError:
        return []


def _guard(request, scope, key):
    """Common checks for every write: permission and an optional digest."""
    if not _editable(scope):
        messages.error(request, f"The API token may not change the {scope.label} firewall "
                                f"(needs {scope.edit_privilege}).")
        return False
    digest = request.POST.get("digest", "")
    if digest and not DIGEST_RE.match(digest):
        raise Http404
    return True


def _with_digest(request, data):
    digest = request.POST.get("digest", "")
    if digest:
        data["digest"] = digest
    return data


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@login_required
def firewall_index(request):
    api, node = _ctx()
    groups, error = [], None
    try:
        groups = api._get("/cluster/firewall/groups") or []
    except ProxmoxAPIError as exc:
        error = exc.message
    return render(request, "firewall/index.html", {
        "groups": groups, "error": error, "can_edit_dc": token_can("/", "Sys.Modify"),
        "node": node, "help_slug": "firewall",
    })


@login_required
def firewall_panel(request, key):
    """HTMX partial: options, rules, aliases and IPSets of one scope."""
    api, node = _ctx()
    scope = _scope(key, node)
    ctx = {"key": key, "scope": scope, "editable": _editable(scope), "error": None,
           "next_url": request.GET.get("next") or reverse("firewall_index"),
           "actions": fw.ACTIONS, "policies": fw.POLICIES, "log_levels": fw.LOG_LEVELS,
           "protocols": fw.PROTOCOLS}
    if not (ctx["next_url"].startswith("/") and not ctx["next_url"].startswith("//")):
        ctx["next_url"] = reverse("firewall_index")
    try:
        rules = api._get(scope.rules_path) or []
        for r in rules:
            r["summary"] = fw.rule_summary(r)
            r["icmp_type"] = r.get("icmp-type", "")
        ctx["rules"] = sorted(rules, key=lambda r: int(r.get("pos", 0)))
        ctx["digest"] = rules[0].get("digest", "") if rules else ""
        if scope.has_options:
            ctx["options"] = api._get(f"{scope.base}/options") or {}
            ctx["options_digest"] = ctx["options"].get("digest", "")
        if scope.has_objects:
            ctx["aliases"] = api._get(f"{scope.base}/aliases") or []
            ipsets = api._get(f"{scope.base}/ipset") or []
            for s in ipsets:
                s["entries"] = api._get(f"{scope.base}/ipset/{quote(s['name'], safe='')}") or []
            ctx["ipsets"] = ipsets
        ctx["macros"] = sorted(_macros(api).items())
        ctx["groups"] = _groups(api) if scope.kind != "group" else []
        dc = api._get("/cluster/firewall/options") or {}
        ctx["dc_enabled"] = str(dc.get("enable", "0")) == "1"
        if scope.kind in ("qemu", "lxc"):
            cfg = api._get(f"/nodes/{node}/{scope.kind}/{scope.vmid}/config") or {}
            nics = sorted(k for k in cfg if re.match(r"^net\d+$", k))
            ctx["nics"] = nics
            ctx["nics_without_fw"] = [n for n in nics if "firewall=1" not in str(cfg[n])]
    except ProxmoxAPIError as exc:
        ctx["error"] = exc.message
    return render(request, "firewall/partials/panel.html", ctx)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

@login_required
@require_POST
def options_save(request, key):
    api, node = _ctx()
    scope = _scope(key, node)
    if not scope.has_options or not _guard(request, scope, key):
        return _back(request, key)
    try:
        data = fw.parse_options_form(request.POST, scope)
        api._put(f"{scope.base}/options", _with_digest(request, data))
        logger.info("firewall options %s by %s: %s", key, request.user, data)
        messages.success(request, f"{scope.label} firewall options saved.")
    except fw.FirewallError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not save options: {exc.message}")
    return _back(request, key)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

@login_required
@require_POST
def rule_add(request, key):
    api, node = _ctx()
    scope = _scope(key, node)
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        data = fw.parse_rule_form(request.POST, scope, _macros(api), _groups(api))
        api._post(scope.rules_path, data)
        logger.info("firewall rule add %s by %s: %s", key, request.user, data)
        messages.success(request, "Rule added (at the top of the list).")
    except fw.FirewallError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not add the rule: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def rule_edit(request, key, pos):
    api, node = _ctx()
    scope = _scope(key, node)
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        data = fw.parse_rule_form(request.POST, scope, _macros(api), _groups(api))
        # Fields left empty must be removed from the existing rule.
        optional = ("macro", "proto", "source", "dest", "sport", "dport", "icmp-type", "iface", "log", "comment")
        delete = [k for k in optional if k not in data or data[k] == ""]
        if delete:
            data["delete"] = ",".join(delete)
        api._put(f"{scope.rules_path}/{int(pos)}", _with_digest(request, data))
        logger.info("firewall rule edit %s/%d by %s", key, pos, request.user)
        messages.success(request, f"Rule {pos} updated.")
    except fw.FirewallError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not update the rule: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def rule_toggle(request, key, pos):
    api, node = _ctx()
    scope = _scope(key, node)
    if not _guard(request, scope, key):
        return _back(request, key)
    enable = 1 if request.POST.get("enable") == "1" else 0
    try:
        api._put(f"{scope.rules_path}/{int(pos)}", _with_digest(request, {"enable": enable}))
        messages.success(request, f"Rule {pos} {'enabled' if enable else 'disabled'}.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not change the rule: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def rule_move(request, key, pos):
    api, node = _ctx()
    scope = _scope(key, node)
    if not _guard(request, scope, key):
        return _back(request, key)
    target = request.POST.get("moveto", "")
    if not target.isdigit():
        raise Http404
    try:
        api._put(f"{scope.rules_path}/{int(pos)}", _with_digest(request, {"moveto": int(target)}))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not move the rule: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def rule_delete(request, key, pos):
    api, node = _ctx()
    scope = _scope(key, node)
    if not _guard(request, scope, key):
        return _back(request, key)
    digest = request.POST.get("digest", "")
    try:
        path = f"{scope.rules_path}/{int(pos)}" + (f"?digest={digest}" if digest else "")
        api._delete(path)
        logger.info("firewall rule delete %s/%d by %s", key, pos, request.user)
        messages.success(request, f"Rule {pos} deleted.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not delete the rule: {exc.message}")
    return _back(request, key)


# ---------------------------------------------------------------------------
# Aliases and IPSets (cluster and guest level)
# ---------------------------------------------------------------------------

def _objects_scope(request, key):
    api, node = _ctx()
    scope = _scope(key, node)
    if not scope.has_objects:
        raise Http404
    return api, scope


@login_required
@require_POST
def alias_add(request, key):
    api, scope = _objects_scope(request, key)
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        data = fw.parse_alias_form(request.POST)
        api._post(f"{scope.base}/aliases", data)
        messages.success(request, f"Alias {data['name']} added.")
    except fw.FirewallError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not add the alias: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def alias_delete(request, key, name):
    api, scope = _objects_scope(request, key)
    if not fw.NAME_RE.match(name):
        raise Http404
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        api._delete(f"{scope.base}/aliases/{quote(name, safe='')}")
        messages.success(request, f"Alias {name} deleted.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not delete the alias: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def ipset_add(request, key):
    api, scope = _objects_scope(request, key)
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        data = fw.parse_ipset_form(request.POST)
        api._post(f"{scope.base}/ipset", data)
        messages.success(request, f"IPSet {data['name']} created.")
    except fw.FirewallError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not create the IPSet: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def ipset_delete(request, key, name):
    api, scope = _objects_scope(request, key)
    if not fw.NAME_RE.match(name):
        raise Http404
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        api._delete(f"{scope.base}/ipset/{quote(name, safe='')}")
        messages.success(request, f"IPSet {name} deleted.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not delete the IPSet (it must be empty): {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def ipset_entry_add(request, key, name):
    api, scope = _objects_scope(request, key)
    if not fw.NAME_RE.match(name):
        raise Http404
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        data = fw.parse_ipset_entry(request.POST)
        api._post(f"{scope.base}/ipset/{quote(name, safe='')}", data)
        messages.success(request, f"{data['cidr']} added to {name}.")
    except fw.FirewallError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not add the entry: {exc.message}")
    return _back(request, key)


@login_required
@require_POST
def ipset_entry_remove(request, key, name):
    api, scope = _objects_scope(request, key)
    if not fw.NAME_RE.match(name):
        raise Http404
    try:
        cidr = fw.parse_ipset_entry({"cidr": request.POST.get("cidr", "")})["cidr"]
    except fw.FirewallError:
        raise Http404
    if not _guard(request, scope, key):
        return _back(request, key)
    try:
        api._delete(f"{scope.base}/ipset/{quote(name, safe='')}/{quote(cidr, safe='')}")
        messages.success(request, f"{cidr} removed from {name}.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not remove the entry: {exc.message}")
    return _back(request, key)


# ---------------------------------------------------------------------------
# Security groups (cluster level, needs Sys.Modify)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def group_add(request):
    api, node = _ctx()
    scope = fw.Scope("cluster")
    if not _guard(request, scope, "dc"):
        return redirect("firewall_index")
    name = (request.POST.get("group") or "").strip()
    if not fw.GROUP_RE.match(name):
        messages.error(request, "Group name: 2-18 letters, digits, _ or - (starts with a letter).")
        return redirect("firewall_index")
    try:
        api._post("/cluster/firewall/groups", {"group": name, "comment": fw._one_line(request.POST.get("comment"), "Comment")})
        messages.success(request, f"Security group {name} created.")
    except (fw.FirewallError, ProxmoxAPIError) as exc:
        messages.error(request, f"Could not create the group: {getattr(exc, 'message', exc)}")
    return redirect("firewall_index")


@login_required
@require_POST
def group_delete(request, name):
    api, node = _ctx()
    if not fw.GROUP_RE.match(name):
        raise Http404
    if not _guard(request, fw.Scope("cluster"), "dc"):
        return redirect("firewall_index")
    try:
        api._delete(f"/cluster/firewall/groups/{quote(name, safe='')}")
        messages.success(request, f"Security group {name} deleted.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not delete the group (it must be empty and unused): {exc.message}")
    return redirect("firewall_index")
