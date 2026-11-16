"""Datacenter → Backups and Storage (PVE parity, phase 3)."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.backups import logic as bl
from apps.proxmox.api import ProxmoxAPIError
from apps.proxmox.perms import token_can
from apps.wizard.models import ProxmoxConfig

logger = logging.getLogger(__name__)


def _ctx():
    config = ProxmoxConfig.objects.filter(is_configured=True).first()
    if config is None:
        raise Http404("Proxmox is not configured")
    return config, config.get_api_client(), config.default_node


def _upid(result):
    return result if isinstance(result, str) and result.startswith("UPID:") else ""


def _guests(api):
    """{vmid: {'name':…, 'type': 'qemu'|'lxc', 'status':…}}"""
    out = {}
    for g in api._get("/cluster/resources", params={"type": "vm"}) or []:
        try:
            out[int(g["vmid"])] = {"name": g.get("name", ""), "type": g.get("type", ""),
                                   "status": g.get("status", ""), "template": g.get("template", 0)}
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _storages(api, node):
    return [s for s in api.get_storage(node) if s.get("enabled", 1) and s.get("active", 1)]


def _backup_storages(api, node):
    return [s for s in _storages(api, node) if "backup" in (s.get("content") or "")]


def _list_backups(api, node, storages, vmid=None):
    items, errors = [], []
    for s in storages:
        try:
            items += [i for i in api.get_content(node, s["storage"], content="backup", vmid=vmid)]
        except ProxmoxAPIError as exc:
            errors.append(f"{s['storage']}: {exc.message}")
    items.sort(key=lambda i: i.get("ctime", 0), reverse=True)
    return items, errors


def _can_delete_backup(storage, vmid):
    return token_can(f"/storage/{storage}", "Datastore.Allocate") or (
        token_can(f"/storage/{storage}", "Datastore.AllocateSpace")
        and token_can(f"/vms/{vmid}", "VM.Backup"))


def _after(request, default):
    nxt = request.POST.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(default)


# ---------------------------------------------------------------------------
# Backups overview
# ---------------------------------------------------------------------------

@login_required
def backups_index(request):
    config, api, node = _ctx()
    error = None
    jobs, backups, storages, guests, errors = [], [], [], {}, []
    vmid = request.GET.get("vmid", "").strip()
    vmid = int(vmid) if vmid.isdigit() else None
    storage_filter = request.GET.get("storage", "")
    try:
        guests = _guests(api)
        storages = _backup_storages(api, node)
        wanted = [s for s in storages if not storage_filter or s["storage"] == storage_filter]
        raw, errors = _list_backups(api, node, wanted, vmid)
        backups = [bl.describe_volume(i, guests) for i in raw]
        for b in backups:
            b["can_delete"] = _can_delete_backup(b["storage"], b["vmid"])
        jobs = [bl.describe_job(j) for j in api.get_backup_jobs()]
    except ProxmoxAPIError as exc:
        error = exc.message
    total = sum(int(b.get("size") or 0) for b in backups)
    return render(request, "backups/index.html", {
        "jobs": jobs, "backups": backups, "storages": storages, "error": error, "errors": errors,
        "filter_vmid": vmid or "", "filter_storage": storage_filter, "total_size": bl.fmt_bytes(total),
        "can_edit_jobs": token_can("/", "Sys.Modify"), "help_slug": "backups",
    })


# ---------------------------------------------------------------------------
# Backup now
# ---------------------------------------------------------------------------

@login_required
def backup_new(request):
    config, api, node = _ctx()
    guests, storages, error = {}, [], None
    try:
        guests = _guests(api)
        storages = _backup_storages(api, node)
    except ProxmoxAPIError as exc:
        error = exc.message
    preselect = {int(v) for v in request.GET.getlist("vmid") if v.isdigit()}

    if request.method == "POST" and not error:
        try:
            params = bl.parse_backup_form(request.POST, guests, {s["storage"] for s in storages})
            upid = _upid(api.vzdump(node, **params))
            logger.info("backup_new %s by %s", params.get("vmid"), request.user)
            messages.success(request, f"Backup of {params['vmid']} started.")
            if upid:
                return redirect("task_detail", upid=upid)
            return redirect("backups_index")
        except bl.BackupError as exc:
            error = str(exc)
        except ProxmoxAPIError as exc:
            error = f"Backup could not start: {exc.message}"
        preselect = {int(v) for v in request.POST.getlist("vmid") if v.isdigit()}

    guest_list = sorted(({"vmid": k, **v} for k, v in guests.items()), key=lambda g: g["vmid"])
    return render(request, "backups/new.html", {
        "guests": guest_list, "storages": storages, "preselect": preselect, "error": error,
        "modes": bl.MODES, "compress": bl.COMPRESS, "post": request.POST if request.method == "POST" else {},
        "help_slug": "backups",
    })


@login_required
@require_POST
def backup_job_run(request, job_id):
    if not bl.JOB_ID_RE.match(job_id):
        raise Http404
    config, api, node = _ctx()
    try:
        job = api.get_backup_job(job_id)
        params = bl.job_run_params(job)
        upid = _upid(api.vzdump(node, **params))
        logger.info("backup_job_run %s by %s", job_id, request.user)
        note = " The job's hook script is not run (only root@pam may set it)." if job.get("script") else ""
        messages.success(request, "Backup job started." + note)
        if upid:
            return redirect("task_detail", upid=upid)
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not run the job: {exc.message}")
    return redirect("backups_index")


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

@login_required
def backup_restore(request):
    volid = request.GET.get("volid") or request.POST.get("volid", "")
    storage = bl.valid_volid(volid)
    if not storage:
        raise Http404("Invalid volume")
    config, api, node = _ctx()
    error = None
    info = bl.describe_volume({"volid": volid})
    if not info["subtype"] or not info["vmid"]:
        raise Http404("Not a vzdump backup")
    kind = info["subtype"]
    guests, config_lines, target_storages, unprivileged = {}, [], [], True
    try:
        guests = _guests(api)
        attrs = api.get_volume_attributes(node, storage, volid) or {}
        info = bl.describe_volume({**attrs, "volid": volid}, guests)
        try:
            cfg_text = api.extract_backup_config(node, volid)
            config_lines = bl.summarize_config(cfg_text if isinstance(cfg_text, str) else "")
            unprivileged = any(l.replace(" ", "") == "unprivileged:1" for l in config_lines)
        except ProxmoxAPIError as exc:
            config_lines = [f"(could not read the configuration: {exc.message})"]
        wanted = "rootdir" if kind == "lxc" else "images"
        target_storages = [s for s in _storages(api, node) if wanted in (s.get("content") or "")]
    except ProxmoxAPIError as exc:
        error = exc.message

    if request.method == "POST" and not error:
        try:
            opts = bl.parse_restore_form(request.POST, kind, set(guests), info["vmid"])
            if opts["storage"] and opts["storage"] not in {s["storage"] for s in target_storages}:
                raise bl.BackupError("Choose a storage that accepts "
                                     f"{'container volumes' if kind == 'lxc' else 'VM disks'}.")
            existing = guests.get(opts["vmid"])
            if existing and existing.get("type") != kind:
                raise bl.BackupError(f"ID {opts['vmid']} is a {'VM' if existing['type'] == 'qemu' else 'container'}; "
                                     "a backup can only replace a guest of the same kind.")
            if existing and existing.get("status") == "running":
                raise bl.BackupError(f"Stop {opts['vmid']} before restoring over it.")
            if kind == "qemu":
                upid = api.restore_vm(node, opts["vmid"], volid, opts["storage"], opts["force"],
                                      opts["unique"], opts["start"])
            else:
                upid = api.restore_lxc(node, opts["vmid"], volid, opts["storage"], opts["force"],
                                       opts["unique"], opts["start"], opts.get("unprivileged"))
            logger.info("backup_restore %s -> %s (force=%s) by %s", volid, opts["vmid"], opts["force"], request.user)
            messages.success(request, f"Restoring to {opts['vmid']}…")
            upid = _upid(upid)
            if upid:
                return redirect("task_detail", upid=upid)
            return redirect("backups_index")
        except bl.BackupError as exc:
            error = str(exc)
        except ProxmoxAPIError as exc:
            error = f"Restore failed: {exc.message}"

    suggested = info["vmid"]
    if suggested in guests:
        free = [v for v in range(100, 1000000) if v not in guests]
        suggested = free[0] if free else info["vmid"]
    return render(request, "backups/restore.html", {
        "volid": volid, "info": info, "kind": kind, "config_lines": config_lines, "error": error,
        "target_storages": target_storages, "suggested_vmid": request.POST.get("target_vmid") or suggested,
        "source_exists": info["vmid"] in guests, "unprivileged": unprivileged, "post": request.POST,
        "help_slug": "backups",
    })


# ---------------------------------------------------------------------------
# Protect / notes / delete
# ---------------------------------------------------------------------------

@login_required
@require_POST
def backup_protect(request):
    volid = request.POST.get("volid", "")
    storage = bl.valid_volid(volid)
    if not storage:
        raise Http404
    config, api, node = _ctx()
    protect = request.POST.get("protected") == "1"
    try:
        api.update_volume(node, storage, volid, protected=protect)
        messages.success(request, "Backup protected." if protect else "Protection removed.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not change protection: {exc.message}")
    return _after(request, "backups_index")


@login_required
@require_POST
def backup_notes(request):
    volid = request.POST.get("volid", "")
    storage = bl.valid_volid(volid)
    if not storage:
        raise Http404
    notes = (request.POST.get("notes") or "").strip()
    if len(notes) > 1024:
        messages.error(request, "Notes are limited to 1024 characters.")
        return _after(request, "backups_index")
    config, api, node = _ctx()
    try:
        api.update_volume(node, storage, volid, notes=notes)
        messages.success(request, "Notes saved.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Could not save notes: {exc.message}")
    return _after(request, "backups_index")


@login_required
@require_POST
def volume_delete(request):
    volid = request.POST.get("volid", "")
    storage = bl.valid_volid(volid)
    if not storage:
        raise Http404
    name = volid.split("/")[-1].split(":")[-1]
    if (request.POST.get("confirm") or "").strip() != name:
        messages.error(request, "Type the file name to confirm the deletion.")
        return _after(request, "backups_index")
    config, api, node = _ctx()
    try:
        attrs = api.get_volume_attributes(node, storage, volid) or {}
        if attrs.get("protected"):
            messages.error(request, "This backup is protected. Remove the protection first.")
            return _after(request, "backups_index")
        api.delete_volume(node, storage, volid)
        logger.info("volume_delete %s by %s", volid, request.user)
        messages.success(request, f"Deleted {name}.")
    except ProxmoxAPIError as exc:
        if exc.status_code == 403:
            messages.error(request, "Proxmox refused: the API token is not allowed to delete this volume.")
        else:
            messages.error(request, f"Delete failed: {exc.message}")
    return _after(request, "backups_index")


# ---------------------------------------------------------------------------
# Per-guest backup card (VM / CT detail pages)
# ---------------------------------------------------------------------------

@login_required
def guest_backups(request, kind, vmid):
    if kind not in ("qemu", "lxc"):
        raise Http404
    config, api, node = _ctx()
    backups, storages, error = [], [], None
    try:
        storages = _backup_storages(api, node)
        raw, errors = _list_backups(api, node, storages, vmid)
        backups = [bl.describe_volume(i) for i in raw if (i.get("subtype") or kind) == kind]
        for b in backups:
            b["can_delete"] = _can_delete_backup(b["storage"], vmid)
        if errors:
            error = "; ".join(errors)
    except ProxmoxAPIError as exc:
        error = exc.message
    detail = reverse("vm_detail", args=[vmid]) if kind == "qemu" else reverse("lxc_detail", args=[vmid])
    return render(request, "backups/partials/guest_backups.html", {
        "backups": backups, "storages": storages, "error": error, "vmid": vmid, "kind": kind,
        "modes": bl.MODES, "compress": bl.COMPRESS, "next_url": detail + "#backups",
    })


@login_required
@require_POST
def guest_backup_now(request, kind, vmid):
    if kind not in ("qemu", "lxc"):
        raise Http404
    config, api, node = _ctx()
    detail = reverse("vm_detail", args=[vmid]) if kind == "qemu" else reverse("lxc_detail", args=[vmid])
    try:
        storages = {s["storage"] for s in _backup_storages(api, node)}
        data = request.POST.copy()
        data.setlist("vmid", [str(vmid)])
        params = bl.parse_backup_form(data, {vmid: {}}, storages)
        upid = _upid(api.vzdump(node, **params))
        logger.info("guest_backup_now %s by %s", vmid, request.user)
        messages.success(request, f"Backup of {vmid} started.")
        if upid:
            return redirect("task_detail", upid=upid)
    except bl.BackupError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Backup could not start: {exc.message}")
    return redirect(detail + "#backups")


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@login_required
def storage_list(request):
    config, api, node = _ctx()
    storages, error = [], None
    try:
        for s in api.get_storage(node):
            total = int(s.get("total") or 0)
            used = int(s.get("used") or 0)
            s["pct"] = round(100 * used / total, 1) if total else 0
            s["used_h"], s["total_h"], s["avail_h"] = bl.fmt_bytes(used), bl.fmt_bytes(total), bl.fmt_bytes(s.get("avail"))
            s["content_list"] = [c for c in (s.get("content") or "").split(",") if c]
            storages.append(s)
    except ProxmoxAPIError as exc:
        error = exc.message
    return render(request, "backups/storage_list.html", {
        "storages": storages, "error": error, "labels": bl.CONTENT_LABELS, "help_slug": "storage",
    })


@login_required
def storage_content(request, storage):
    if not bl.valid_storage(storage):
        raise Http404
    config, api, node = _ctx()
    error, items, info = None, [], None
    content = request.GET.get("content", "")
    try:
        info = next((s for s in api.get_storage(node) if s.get("storage") == storage), None)
        if info is None:
            raise Http404("Unknown storage")
        types = [c for c in (info.get("content") or "").split(",") if c]
        if content not in types:
            content = types[0] if types else ""
        guests = _guests(api)
        raw = api.get_content(node, storage, content=content) if content else []
        items = [bl.describe_volume(i, guests) for i in raw]
        items.sort(key=lambda i: (i.get("vmid") or 0, i["name"]))
        can_allocate = token_can(f"/storage/{storage}", "Datastore.Allocate")
        for i in items:
            if content == "backup":
                i["can_delete"] = _can_delete_backup(storage, i["vmid"])
            elif content in ("images", "rootdir"):
                # Disks are removed from the VM/CT page; only orphans here.
                i["can_delete"] = can_allocate and not i["guest_exists"]
            else:
                i["can_delete"] = can_allocate
    except ProxmoxAPIError as exc:
        error = exc.message
        types = []
    return render(request, "backups/storage_content.html", {
        "storage": storage, "info": info, "items": items, "content": content, "types": types,
        "labels": bl.CONTENT_LABELS, "error": error, "next_url": request.get_full_path(),
        "help_slug": "storage",
    })
