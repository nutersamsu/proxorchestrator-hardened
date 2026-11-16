"""Proxmox task history and live task logs (the PVE "Tasks" panel)."""

import logging
import re
from datetime import datetime
from datetime import timezone as dt_timezone

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.proxmox.api import ProxmoxAPIError

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
LOG_LIMIT = 5000

# UPID:<node>:<pid>:<pstart>:<starttime>:<type>:<id>:<user>:
UPID_RE = re.compile(
    r"^UPID:(?P<node>[A-Za-z0-9.-]+):[0-9A-Fa-f]{8}:[0-9A-Fa-f]{8}:(?P<start>[0-9A-Fa-f]{8}):"
    r"(?P<type>[A-Za-z0-9_.-]+):(?P<id>[A-Za-z0-9_.@-]*):(?P<user>[A-Za-z0-9_.@!-]+):$"
)

# Human-readable task names (subset of the PVE web UI table).
TASK_TYPES = {
    "acmenewcert": "Order certificate",
    "aptupdate": "Update package database",
    "clustercreate": "Create cluster",
    "download": "Download",
    "imgcopy": "Copy disk image",
    "qmclone": "VM clone",
    "qmconfig": "VM configure",
    "qmcreate": "VM create",
    "qmdelsnapshot": "VM delete snapshot",
    "qmdestroy": "VM destroy",
    "qmigrate": "VM migrate",
    "qmmove": "VM move disk",
    "qmpause": "VM pause",
    "qmreboot": "VM reboot",
    "qmreset": "VM reset",
    "qmrestore": "VM restore",
    "qmresume": "VM resume",
    "qmrollback": "VM rollback",
    "qmshutdown": "VM shutdown",
    "qmsnapshot": "VM snapshot",
    "qmstart": "VM start",
    "qmstop": "VM stop",
    "qmsuspend": "VM hibernate",
    "qmtemplate": "Convert to template",
    "resize": "Resize disk",
    "move_volume": "CT move volume",
    "pull_file": "Pull file",
    "spiceproxy": "SPICE console",
    "srvreload": "Reload service",
    "srvrestart": "Restart service",
    "srvstart": "Start service",
    "srvstop": "Stop service",
    "startall": "Bulk start guests",
    "stopall": "Bulk shutdown guests",
    "suspendall": "Bulk suspend guests",
    "unknownimgdel": "Destroy image",
    "imgdel": "Erase data",
    "vncproxy": "Console",
    "vncshell": "Shell",
    "termproxy": "Console (xterm.js)",
    "vzclone": "CT clone",
    "vzcreate": "CT create",
    "vzdelsnapshot": "CT delete snapshot",
    "vzdestroy": "CT destroy",
    "vzdump": "Backup",
    "vzmigrate": "CT migrate",
    "vzmount": "CT mount",
    "vzreboot": "CT reboot",
    "vzrestore": "CT restore",
    "vzresume": "CT resume",
    "vzrollback": "CT rollback",
    "vzshutdown": "CT shutdown",
    "vzsnapshot": "CT snapshot",
    "vzstart": "CT start",
    "vzstop": "CT stop",
    "vzsuspend": "CT suspend",
    "vztemplate": "Convert to template",
    "vzumount": "CT unmount",
    "zfscreate": "ZFS storage create",
    "lvmcreate": "LVM storage create",
    "lvmthincreate": "LVM-thin storage create",
    "dircreate": "Directory storage create",
    "diskinit": "Initialize disk",
    "wipedisk": "Wipe disk",
}


def _config():
    from apps.wizard.models import ProxmoxConfig
    return ProxmoxConfig.objects.filter(is_configured=True).first()


def parse_upid(upid):
    """Validate a UPID and return its fields, or raise Http404."""
    m = UPID_RE.match(upid or "")
    if not m:
        raise Http404("Invalid task id")
    return m.groupdict()


def _ts(value):
    try:
        return timezone.localtime(datetime.fromtimestamp(int(value), tz=dt_timezone.utc))
    except (TypeError, ValueError, OSError):
        return None


def _duration(start, end):
    if not start or not end:
        return ""
    secs = int((end - start).total_seconds())
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def describe(task):
    """Decorate a raw PVE task dict for the templates."""
    ttype = task.get("type", "")
    tid = task.get("id", "")
    label = TASK_TYPES.get(ttype, ttype)
    start = _ts(task.get("starttime"))
    end = _ts(task.get("endtime")) if task.get("endtime") else None
    status = task.get("status")
    running = not end and status in (None, "", "running")
    ok = status == "OK"
    warning = bool(status) and status.startswith("WARNINGS")
    user = task.get("user", "")
    if task.get("tokenid"):
        user = f"{user}!{task['tokenid']}"
    return {
        **task,
        "label": f"{label} {tid}".strip() if tid else label,
        "type_label": label,
        "start": start,
        "end": end,
        "duration": _duration(start, end),
        "running": running,
        "ok": ok,
        "warning": warning,
        "failed": bool(status) and not ok and not warning and not running,
        "status_text": "running" if running else (status or ""),
        "user_display": user,
        "guest_url": _guest_url(ttype, tid),
    }


def _guest_url(ttype, tid):
    if not tid or not str(tid).isdigit():
        return ""
    if ttype.startswith("qm"):
        return reverse("vm_detail", args=[int(tid)])
    if ttype.startswith("vz") and ttype != "vzdump":
        return reverse("lxc_detail", args=[int(tid)])
    return ""


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def task_list(request):
    config = _config()
    if config is None:
        return redirect("dashboard")

    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        page = 1
    vmid = request.GET.get("vmid", "").strip()
    vmid = vmid if vmid.isdigit() else ""
    typefilter = request.GET.get("type", "").strip()
    typefilter = typefilter if re.fullmatch(r"[a-z_]{1,32}", typefilter or "") else ""
    userfilter = request.GET.get("user", "").strip()
    userfilter = userfilter if re.fullmatch(r"[A-Za-z0-9_.@!-]{1,64}", userfilter or "") else ""
    errors = request.GET.get("errors") == "1"
    running_only = request.GET.get("running") == "1"

    error = None
    tasks = []
    total = 0
    try:
        total, raw = config.get_api_client().get_tasks(
            config.default_node,
            start=(page - 1) * PAGE_SIZE,
            limit=PAGE_SIZE,
            vmid=vmid or None,
            typefilter=typefilter or None,
            userfilter=userfilter or None,
            errors=errors,
            source="active" if running_only else "all",
        )
        tasks = [describe(t) for t in raw]
    except ProxmoxAPIError as exc:
        error = exc.message

    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "tasks/list.html", {
        "tasks": tasks,
        "total": total,
        "page": page,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
        "query": query.urlencode(),
        "filters": {"vmid": vmid, "type": typefilter, "user": userfilter,
                    "errors": errors, "running": running_only},
        "type_choices": sorted(TASK_TYPES.items(), key=lambda kv: kv[1]),
        "error": error,
        "help_slug": "tasks",
    })


@login_required
def task_detail(request, upid):
    fields = parse_upid(upid)
    config = _config()
    if config is None:
        return redirect("dashboard")
    task = describe({
        "upid": upid,
        "type": fields["type"],
        "id": fields["id"],
        "user": fields["user"],
        "node": fields["node"],
        "starttime": int(fields["start"], 16),
    })
    return render(request, "tasks/detail.html", {"task": task, "upid": upid, "help_slug": "tasks"})


@login_required
def task_log(request, upid):
    """HTMX partial: status + full log; keeps polling while the task runs."""
    fields = parse_upid(upid)
    config = _config()
    if config is None:
        return HttpResponse(status=204)
    api = config.get_api_client()
    node = fields["node"]
    error = None
    status = {}
    lines = []
    total = 0
    try:
        status = api.get_task_status_by_upid(node, upid) or {}
        total, lines = api.get_task_log(node, upid, start=0, limit=LOG_LIMIT)
    except ProxmoxAPIError as exc:
        error = exc.message

    running = status.get("status") == "running"
    exitstatus = status.get("exitstatus", "")
    return render(request, "tasks/partials/task_log.html", {
        "upid": upid,
        "error": error,
        "running": running,
        "exitstatus": exitstatus,
        "ok": exitstatus == "OK",
        "warning": str(exitstatus).startswith("WARNINGS"),
        "lines": [ln.get("t", "") for ln in lines],
        "truncated": total > LOG_LIMIT,
        "total": total,
        "start": _ts(status.get("starttime")),
    })


@login_required
@require_POST
def task_stop(request, upid):
    fields = parse_upid(upid)
    config = _config()
    if config is None:
        return redirect("dashboard")
    try:
        config.get_api_client().stop_task(fields["node"], upid)
        logger.info("Task %s stopped by %s", upid, request.user)
        messages.success(request, "Stop requested.")
    except ProxmoxAPIError as exc:
        if exc.status_code == 403:
            messages.error(request, "Proxmox refused: the API token may only stop tasks it started itself.")
        else:
            messages.error(request, f"Could not stop the task: {exc.message}")
    return redirect("task_detail", upid=upid)


@login_required
def tasks_recent(request):
    """HTMX partial for the task bar at the bottom of every page."""
    config = _config()
    if config is None:
        return HttpResponse("")
    try:
        _, raw = config.get_api_client().get_tasks(config.default_node, start=0, limit=6)
        tasks = [describe(t) for t in raw]
        error = None
    except ProxmoxAPIError as exc:
        tasks, error = [], exc.message
    return render(request, "tasks/partials/recent.html", {"tasks": tasks, "error": error})
