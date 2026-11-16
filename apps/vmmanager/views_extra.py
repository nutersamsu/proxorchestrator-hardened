"""VM pages added for PVE parity: Options, Cloud-Init, guest agent info,
move disk and convert to template."""

import logging


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.proxmox.api import ProxmoxAPIError
from apps.proxmox.perms import token_can
from apps.vmmanager import vm_options as vo
from apps.wizard.models import ProxmoxConfig

logger = logging.getLogger(__name__)


def _api():
    config = ProxmoxConfig.get_config()
    return config, config.get_api_client(), config.default_node


def _upid(result):
    return result if isinstance(result, str) and result.startswith("UPID:") else ""


def _to_task_or_detail(request, upid, vmid, ok_message):
    messages.success(request, ok_message)
    if upid:
        return redirect("task_detail", upid=upid)
    return redirect("vm_detail", vmid=vmid)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

@login_required
@require_POST
def vm_options_save(request, vmid):
    try:
        kwargs, delete = vo.parse_options_form(request.POST)
    except vo.OptionError as exc:
        messages.error(request, str(exc))
        return redirect("vm_detail", vmid=vmid)
    try:
        _, api, node = _api()
        kwargs, delete = vo.only_changes(api.get_vm_config(node, vmid), kwargs, delete)
        if ("startup" in kwargs or "startup" in delete) and not token_can("/", "Sys.Modify"):
            messages.error(request, "Changing the start/shutdown order needs the Sys.Modify privilege, "
                                    "which the API token does not have. Nothing was saved.")
            return redirect("vm_detail", vmid=vmid)
        if not kwargs and not delete:
            messages.info(request, "No changes.")
            return redirect("vm_detail", vmid=vmid)
        if delete:
            kwargs["delete"] = ",".join(delete)
        api.update_vm_config(node, vmid, **kwargs)
        status = api.get_vm_status(node, vmid)
        if status.get("status") == "running":
            messages.warning(request, "Options saved. Some changes (display, SCSI controller, "
                                      "ACPI, KVM, agent) apply after the next full stop/start.")
        else:
            messages.success(request, "Options saved.")
        logger.info("vm_options vmid=%d updated by %s", vmid, request.user)
    except ProxmoxAPIError as exc:
        messages.error(request, f"Failed to save options: {exc.message}")
    return redirect("vm_detail", vmid=vmid)


# ---------------------------------------------------------------------------
# Cloud-init
# ---------------------------------------------------------------------------

@login_required
def vm_cloudinit(request, vmid):
    """HTMX partial: cloud-init form (or offer to add a cloud-init drive)."""
    error = None
    ci = None
    pending = set()
    storage_pools = []
    try:
        _, api, node = _api()
        raw = api.get_vm_config(node, vmid)
        ci = vo.cloudinit_fields(raw)
        if ci["drive"]:
            try:
                pending = {i.get("key") for i in api.get_cloudinit_pending(node, vmid)
                           if "pending" in i or i.get("delete")}
            except ProxmoxAPIError:
                pending = set()
        else:
            storage_pools = [s for s in api.get_storage(node) if "images" in (s.get("content") or "")]
    except ProxmoxAPIError as exc:
        error = exc.message
    return render(request, "vmmanager/partials/vm_cloudinit.html", {
        "vmid": vmid, "ci": ci, "error": error, "pending": sorted(pending),
        "citypes": vo.CITYPES, "storage_pools": storage_pools,
    })


@login_required
@require_POST
def vm_cloudinit_save(request, vmid):
    try:
        _, api, node = _api()
        raw = api.get_vm_config(node, vmid)
        kwargs, delete = vo.parse_cloudinit_form(request.POST, raw)
        if delete:
            kwargs["delete"] = ",".join(delete)
        api.update_vm_config(node, vmid, **kwargs)
        if request.POST.get("regenerate") == "1":
            api.regenerate_cloudinit(node, vmid)
            messages.success(request, "Cloud-init saved and image regenerated. "
                                      "The guest applies it on the next boot.")
        else:
            messages.success(request, "Cloud-init saved. Click “Regenerate image” (or restart the "
                                      "VM) so the guest sees the new values.")
        logger.info("vm_cloudinit vmid=%d updated by %s", vmid, request.user)
    except vo.OptionError as exc:
        messages.error(request, str(exc))
    except ProxmoxAPIError as exc:
        messages.error(request, f"Failed to save cloud-init: {exc.message}")
    return redirect(f"/vm/{vmid}/#cloudinit")


@login_required
@require_POST
def vm_cloudinit_regenerate(request, vmid):
    try:
        _, api, node = _api()
        api.regenerate_cloudinit(node, vmid)
        messages.success(request, "Cloud-init image regenerated.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Failed to regenerate the image: {exc.message}")
    return redirect(f"/vm/{vmid}/#cloudinit")


@login_required
@require_POST
def vm_cloudinit_add(request, vmid):
    storage = request.POST.get("storage", "")
    if not vo.valid_storage(storage):
        messages.error(request, "Choose a storage for the cloud-init drive.")
        return redirect(f"/vm/{vmid}/#cloudinit")
    try:
        _, api, node = _api()
        raw = api.get_vm_config(node, vmid)
        if vo.find_cloudinit_drive(raw):
            messages.info(request, "The VM already has a cloud-init drive.")
            return redirect(f"/vm/{vmid}/#cloudinit")
        slot = next((f"ide{i}" for i in (2, 0, 1, 3) if f"ide{i}" not in raw), None) or \
            next((f"sata{i}" for i in range(6) if f"sata{i}" not in raw), None)
        if not slot:
            messages.error(request, "No free IDE/SATA slot for the cloud-init drive.")
            return redirect(f"/vm/{vmid}/#cloudinit")
        api.update_vm_config(node, vmid, **{slot: f"{storage}:cloudinit"})
        messages.success(request, f"Cloud-init drive added on {slot}.")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Failed to add the cloud-init drive: {exc.message}")
    return redirect(f"/vm/{vmid}/#cloudinit")


# ---------------------------------------------------------------------------
# Guest agent
# ---------------------------------------------------------------------------

def _fmt_bytes(b):
    b = float(b or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if b < 1024 or unit == "TiB":
            return f"{b:.1f} {unit}"
        b /= 1024


@login_required
def vm_agent_info(request, vmid):
    """HTMX partial: OS, host name, file systems and all IPs from the guest agent."""
    info = {"os": None, "hostname": "", "filesystems": [], "interfaces": []}
    error = None
    try:
        _, api, node = _api()
        try:
            os_raw = api.agent_get(node, vmid, "get-osinfo") or {}
            info["os"] = {str(k).replace("-", "_"): v for k, v in os_raw.items()}
        except ProxmoxAPIError as exc:
            # 500 "QEMU guest agent is not running" is the common case
            error = "Guest agent not running or not enabled in Options." if exc.status_code in (500, 596) else exc.message
            raise
        try:
            info["hostname"] = (api.agent_get(node, vmid, "get-host-name") or {}).get("host-name", "")
        except ProxmoxAPIError:
            pass
        try:
            for fs in api.agent_get(node, vmid, "get-fsinfo") or []:
                total = fs.get("total-bytes")
                used = fs.get("used-bytes")
                if not total or fs.get("type") in ("squashfs", "tmpfs", "overlay"):
                    continue
                info["filesystems"].append({
                    "mount": fs.get("mountpoint", ""), "type": fs.get("type", ""),
                    "used": _fmt_bytes(used), "total": _fmt_bytes(total),
                    "pct": round(100 * (used or 0) / total, 1) if total else 0,
                })
        except ProxmoxAPIError:
            pass
        try:
            for iface in api.get_vm_agent_interfaces(node, vmid) or []:
                name = str(iface.get("name", ""))
                if name == "lo" or name.startswith("veth"):
                    continue
                addrs = [f"{a.get('ip-address')}/{a.get('prefix')}" for a in iface.get("ip-addresses", [])
                         if a.get("ip-address") and not str(a.get("ip-address")).startswith("fe80")]
                if not addrs:
                    continue
                info["interfaces"].append({"name": iface.get("name", ""),
                                           "mac": iface.get("hardware-address", ""),
                                           "addresses": addrs})
        except ProxmoxAPIError:
            pass
    except ProxmoxAPIError as exc:
        if not error:
            error = exc.message
    return render(request, "vmmanager/partials/vm_agent.html", {"info": info, "error": error})


# ---------------------------------------------------------------------------
# Move disk, convert to template
# ---------------------------------------------------------------------------

@login_required
@require_POST
def vm_disk_move(request, vmid):
    disk = request.POST.get("disk", "")
    storage = request.POST.get("storage", "")
    fmt = request.POST.get("format", "")
    if not vo.DISK_KEY_RE.match(disk) or disk.startswith("unused") or not vo.valid_storage(storage):
        messages.error(request, "Invalid disk or storage.")
        return redirect("vm_detail", vmid=vmid)
    if fmt not in ("", "raw", "qcow2", "vmdk"):
        messages.error(request, "Invalid disk format.")
        return redirect("vm_detail", vmid=vmid)
    try:
        _, api, node = _api()
        upid = _upid(api.move_vm_disk(node, vmid, disk, storage,
                                      delete=request.POST.get("delete_source") == "1", fmt=fmt or None))
        logger.info("vm_disk_move vmid=%d %s -> %s by %s", vmid, disk, storage, request.user)
        return _to_task_or_detail(request, upid, vmid, f"Moving {disk} to {storage}…")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Move failed: {exc.message}")
        return redirect("vm_detail", vmid=vmid)


@login_required
@require_POST
def vm_convert_template(request, vmid):
    try:
        _, api, node = _api()
        status = api.get_vm_status(node, vmid)
        if status.get("status") != "stopped":
            messages.error(request, "Stop the VM before converting it to a template.")
            return redirect("vm_detail", vmid=vmid)
        if request.POST.get("confirm_vmid", "").strip() != str(vmid):
            messages.error(request, "Type the VMID to confirm the conversion.")
            return redirect("vm_detail", vmid=vmid)
        upid = _upid(api.convert_vm_to_template(node, vmid))
        logger.info("vm_convert_template vmid=%d by %s", vmid, request.user)
        return _to_task_or_detail(request, upid, vmid, f"Converting VM {vmid} to a template…")
    except ProxmoxAPIError as exc:
        messages.error(request, f"Conversion failed: {exc.message}")
        return redirect("vm_detail", vmid=vmid)
