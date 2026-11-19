"""Container actions added for PVE parity: move volume, convert to template."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.proxmox.api import ProxmoxAPIError
from apps.vmmanager.vm_options import CT_VOLUME_RE
from apps.vmmanager.vm_options import valid_storage
from apps.wizard.models import ProxmoxConfig
from django.utils.translation import gettext

logger = logging.getLogger(__name__)


def _upid(result):
    return result if isinstance(result, str) and result.startswith("UPID:") else ""


@login_required
@require_POST
def lxc_volume_move(request, vmid):
    volume = request.POST.get("volume", "")
    storage = request.POST.get("storage", "")
    if not CT_VOLUME_RE.match(volume) or not valid_storage(storage):
        messages.error(request, gettext("Invalid volume or storage."))
        return redirect("lxc_detail", vmid=vmid)
    config = ProxmoxConfig.get_config()
    node = config.default_node
    try:
        api = config.get_api_client()
        if api.get_lxc_status(node, vmid).get("status") != "stopped" and volume == "rootfs":
            messages.error(request, gettext("Stop the container before moving its root disk."))
            return redirect("lxc_detail", vmid=vmid)
        upid = _upid(api.move_lxc_volume(node, vmid, volume, storage,
                                         delete=request.POST.get("delete_source") == "1"))
        logger.info("lxc_volume_move vmid=%d %s -> %s by %s", vmid, volume, storage, request.user)
        messages.success(request, gettext('Moving %(volume)s to %(storage)s…') % {"volume": volume, "storage": storage})
        if upid:
            return redirect("task_detail", upid=upid)
    except ProxmoxAPIError as exc:
        messages.error(request, gettext('Move failed: %(message)s') % {"message": exc.message})
    return redirect("lxc_detail", vmid=vmid)


@login_required
@require_POST
def lxc_convert_template(request, vmid):
    config = ProxmoxConfig.get_config()
    node = config.default_node
    try:
        api = config.get_api_client()
        if api.get_lxc_status(node, vmid).get("status") != "stopped":
            messages.error(request, gettext("Stop the container before converting it to a template."))
            return redirect("lxc_detail", vmid=vmid)
        if request.POST.get("confirm_vmid", "").strip() != str(vmid):
            messages.error(request, gettext("Type the CT ID to confirm the conversion."))
            return redirect("lxc_detail", vmid=vmid)
        upid = _upid(api.convert_lxc_to_template(node, vmid))
        logger.info("lxc_convert_template vmid=%d by %s", vmid, request.user)
        messages.success(request, gettext('Converting container %(vmid)s to a template…') % {"vmid": vmid})
        if upid:
            return redirect("task_detail", upid=upid)
    except ProxmoxAPIError as exc:
        messages.error(request, gettext('Conversion failed: %(message)s') % {"message": exc.message})
    return redirect("lxc_detail", vmid=vmid)
