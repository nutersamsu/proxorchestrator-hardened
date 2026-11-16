"""RRD performance charts (node, VM, container) — HTMX partial."""

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import render

from apps.core.charts import CONSOLIDATIONS
from apps.core.charts import TIMEFRAMES
from apps.core.charts import build_charts
from apps.proxmox.api import ProxmoxAPIError

logger = logging.getLogger(__name__)

KINDS = ("node", "qemu", "lxc")


@login_required
def rrd_charts(request, kind, vmid=None):
    from apps.wizard.models import ProxmoxConfig

    if kind not in KINDS or (kind != "node") != (vmid is not None):
        raise Http404
    config = ProxmoxConfig.objects.filter(is_configured=True).first()
    if config is None:
        return HttpResponse(status=204)

    timeframe = request.GET.get("timeframe", "hour")
    if timeframe not in TIMEFRAMES:
        timeframe = "hour"
    cf = request.GET.get("cf", "AVERAGE")
    if cf not in CONSOLIDATIONS:
        cf = "AVERAGE"

    error = None
    charts = []
    try:
        samples = config.get_api_client().get_rrddata(
            config.default_node, timeframe=timeframe, cf=cf, kind=kind, vmid=vmid
        )
        charts = build_charts(samples, kind, timeframe, cf)
    except ProxmoxAPIError as exc:
        logger.warning("rrd_charts %s %s: %s", kind, vmid, exc)
        error = exc.message

    base_url = request.path
    return render(request, "core/partials/rrd_charts.html", {
        "charts": charts,
        "error": error,
        "timeframe": timeframe,
        "cf": cf,
        "timeframes": TIMEFRAMES,
        "base_url": base_url,
        "target_id": f"rrd-{kind}-{vmid or 'node'}",
    })
