"""Proxmox node summary for the dashboard.

Mirrors the information of the PVE web UI "Summary" panel of a node (without
the RRD graphs) and adds hardware temperatures, which the PVE API does not
expose. Temperatures are read over the app's existing SSH connection straight
from /sys/class/hwmon, so nothing (lm-sensors etc.) has to be installed on the
host.
"""

import logging
import re

from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_SECONDS = 20

# Fixed script, no user input. Prints one line per sensor:
#   <hwmonN>|<chip name>|<label>|<millidegrees>|<crit millidegrees or empty>
HWMON_SCRIPT = (
    'for d in /sys/class/hwmon/hwmon*; do '
    '[ -r "$d/name" ] || continue; n=$(cat "$d/name"); '
    'for t in "$d"/temp*_input; do [ -r "$t" ] || continue; '
    'b=${t%_input}; '
    'printf "%s|%s|%s|%s|%s\\n" "${d##*/}" "$n" "$(cat "${b}_label" 2>/dev/null)" '
    '"$(cat "$t" 2>/dev/null)" "$(cat "${b}_crit" 2>/dev/null)"; '
    'done; done'
)

CHIP_NAMES = {
    "coretemp": "CPU",
    "k10temp": "CPU",
    "zenpower": "CPU",
    "cpu_thermal": "CPU",
    "nvme": "NVMe",
    "drivetemp": "Disk",
    "acpitz": "ACPI",
    "amdgpu": "GPU",
    "radeon": "GPU",
    "nouveau": "GPU",
}

# Label preferred as the chip's main reading (first match wins).
PRIMARY_LABELS = ("package id 0", "tctl", "tdie", "composite")


def parse_hwmon(text):
    """Parse HWMON_SCRIPT output into a list of sensor dicts."""
    sensors = []
    for line in (text or "").splitlines():
        parts = line.split("|")
        if len(parts) != 5:
            continue
        dev, chip, label, raw, crit = (p.strip() for p in parts)
        try:
            celsius = int(raw) / 1000.0
        except ValueError:
            continue
        # Drivers report bogus values for absent sensors.
        if celsius <= -40 or celsius >= 150:
            continue
        try:
            crit_c = int(crit) / 1000.0 if crit else None
        except ValueError:
            crit_c = None
        if crit_c is not None and not 0 < crit_c < 150:
            crit_c = None
        sensors.append({"dev": dev, "chip": chip, "label": label, "celsius": celsius, "crit": crit_c})
    return sensors


def _friendly_chip(chip):
    if chip.startswith("pch_"):
        return "Chipset"
    if chip.startswith("iwlwifi"):
        return "Wi-Fi"
    return CHIP_NAMES.get(chip, chip)


def temp_level(celsius, crit=None):
    """Return 'ok' / 'warm' / 'hot' for colouring."""
    hot = (crit - 10) if crit else 85
    warm = min(70, hot - 10)
    if celsius >= hot:
        return "hot"
    if celsius >= warm:
        return "warm"
    return "ok"


def summarize_temps(sensors):
    """Reduce raw sensors to one main reading per hwmon chip.

    Returns a list of dicts {name, label, celsius, level, details}, CPU first.
    'details' holds the remaining readings of the chip (e.g. each core).
    """
    by_dev = {}
    for s in sensors:
        by_dev.setdefault(s["dev"], []).append(s)
    groups = list(by_dev.values())

    result = []
    counts = {}
    for group in groups:
        primary = None
        for wanted in PRIMARY_LABELS:
            primary = next((s for s in group if s["label"].lower() == wanted), None)
            if primary:
                break
        if primary is None:
            primary = max(group, key=lambda s: s["celsius"])
        name = _friendly_chip(group[0]["chip"])
        counts[name] = counts.get(name, 0) + 1
        result.append({
            "name": name,
            "label": primary["label"],
            "celsius": round(primary["celsius"], 1),
            "level": temp_level(primary["celsius"], primary["crit"]),
            "details": [
                {"label": s["label"] or s["chip"], "celsius": round(s["celsius"], 1)}
                for s in group if s is not primary
            ],
        })
    # Number duplicated names (NVMe 1, NVMe 2).
    seen = {}
    for item in result:
        if counts[item["name"]] > 1:
            seen[item["name"]] = seen.get(item["name"], 0) + 1
            item["name"] = f"{item['name']} {seen[item['name']]}"
    result.sort(key=lambda t: (not t["name"].startswith("CPU"),))
    return result


def read_temperatures(config):
    """Read temperatures from the node over SSH. Returns (list, error)."""
    try:
        with config.get_ssh_client() as ssh:
            stdout, stderr, code = ssh.run(["sh", "-c", HWMON_SCRIPT])
    except Exception as exc:  # network / auth problems must not break the page
        logger.info("Temperature read failed: %s", exc)
        return [], "SSH unavailable"
    temps = summarize_temps(parse_hwmon(stdout))
    if not temps:
        return [], "No sensors exposed by the host"
    return temps, None



# ---------------------------------------------------------------------------
# Formatting: same strings as the PVE web UI (proxmox-widget-toolkit Utils)
# ---------------------------------------------------------------------------

def _pct(used, total):
    try:
        return round(100.0 * float(used) / float(total), 2) if total else 0.0
    except (TypeError, ValueError):
        return 0.0


def format_bytes(value):
    """Binary units like the PVE UI ("15.48 GiB", "0 B")."""
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(size) < 1024 or unit == "PiB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return "-"


def format_uptime(seconds):
    """PVE format_duration_long: '2 days 22:35:28' / '1 day 01:02:03' / '22:35:28'."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "-"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    clock = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    if days:
        return f"{days} day{'s' if days != 1 else ''} {clock}"
    return clock


def _kernel_text(status):
    """'Linux 7.0.14-28-pve (2026-11-02T11:54Z)' like the PVE Summary."""
    kernel = status.get("current-kernel") or {}
    if kernel.get("sysname") and kernel.get("release"):
        text = f"{kernel['sysname']} {kernel['release']}"
        match = re.search(r"\(([^()]+)\)\s*$", kernel.get("version") or "")
        return f"{text} ({match.group(1)})" if match else text
    return status.get("kversion") or "-"


def build_summary(status):
    """Turn /nodes/{node}/status into template-friendly values."""
    cpuinfo = status.get("cpuinfo") or {}
    boot = status.get("boot-info") or {}
    ksm = status.get("ksm") or {}

    def usage(block):
        block = block or {}
        total = block.get("total") or 0
        used = block.get("used")
        if used is None and total:
            used = total - (block.get("free") or block.get("avail") or 0)
        used = used or 0
        pct = _pct(used, total)
        return {
            "pct": pct,
            "text": f"{pct:.2f}% ({format_bytes(used)} of {format_bytes(total)})",
            "present": bool(total),
        }

    cpus = cpuinfo.get("cpus")
    sockets = cpuinfo.get("sockets")
    model = cpuinfo.get("model") or ""
    cpu_desc = model or "-"
    if cpus:
        cpu_desc = f"{cpus} x {model}" if model else f"{cpus} CPU(s)"
        if sockets:
            cpu_desc += f" ({sockets} Socket{'s' if int(sockets) != 1 else ''})"

    boot_mode = (boot.get("mode") or "").lower()
    if boot_mode == "efi":
        boot_mode = "EFI (Secure Boot)" if boot.get("secureboot") else "EFI"
    elif boot_mode == "legacy-bios":
        boot_mode = "Legacy BIOS"
    else:
        boot_mode = boot_mode.upper() or "-"

    cpu_pct = _pct(status.get("cpu") or 0, 1)
    cpu_text = f"{cpu_pct:.2f}%"
    if cpus:
        cpu_text += f" of {cpus} CPU{'s' if int(cpus) > 1 else ''}"
    io_pct = _pct(status.get("wait") or 0, 1)

    load = status.get("loadavg") or []
    return {
        "cpu_pct": cpu_pct,
        "cpu_text": cpu_text,
        "io_delay_pct": io_pct,
        "io_delay_text": f"{io_pct:.2f}%",
        "loadavg": ",".join(str(x) for x in load) if load else "-",
        "memory": usage(status.get("memory")),
        "swap": usage(status.get("swap")),
        "rootfs": usage(status.get("rootfs")),
        "ksm_shared": format_bytes(ksm.get("shared") or 0),
        "cpu_desc": cpu_desc,
        "kernel": _kernel_text(status),
        "boot_mode": boot_mode,
        "pveversion": status.get("pveversion") or "-",
        "uptime": format_uptime(status.get("uptime")),
    }


def repository_status(repos, subscription_active=None):
    """Summarise /nodes/{node}/apt/repositories like the PVE Summary.

    Returns a list of {level: ok|warning|error, text} or None if unknown.
    """
    if not isinstance(repos, dict):
        return None
    if repos.get("errors"):
        return [{"level": "error", "text": "Error parsing repositories"}]
    enabled = {
        r.get("handle") for r in repos.get("standard-repos") or []
        if r.get("status") == 1 and not str(r.get("handle", "")).startswith("ceph")
    }
    if not enabled:
        return [{"level": "error", "text": "No Proxmox VE repository enabled!"}]
    result = [{"level": "ok", "text": "Proxmox VE updates"}]
    if enabled & {"no-subscription", "test"}:
        result.append({"level": "warning", "text": "Non production-ready repository enabled!"})
    elif "enterprise" in enabled and subscription_active is False:
        result.append({"level": "warning", "text": "Enterprise repository needs valid subscription"})
    return result


def read_repository_status(api, node):
    try:
        repos = api.get_apt_repositories(node)
    except Exception as exc:
        logger.info("Repository status failed: %s", exc)
        return None
    subscription_active = None
    try:
        sub = api.get_subscription(node)
        subscription_active = (sub or {}).get("status", "").lower() == "active"
    except Exception:
        pass
    return repository_status(repos, subscription_active)


def get_node_summary(config, use_cache=True):
    """Return the context for the node summary card (cached briefly)."""
    node = config.default_node
    key = f"po:node-summary:{config.pk}:{node}"
    if use_cache:
        cached = cache.get(key)
        if cached is not None:
            return cached

    data = {"node": node, "summary": None, "error": None, "repos": None,
            "temps": [], "temps_error": None}
    try:
        api = config.get_api_client()
        data["summary"] = build_summary(api.get_node_status(node))
        data["repos"] = read_repository_status(api, node)
    except Exception as exc:
        logger.info("Node status failed: %s", exc)
        msg = str(exc)
        data["error"] = (
            "The API token cannot read the node status (needs Sys.Audit)."
            if "403" in msg else "Could not read the node status from the Proxmox API."
        )
    data["temps"], data["temps_error"] = read_temperatures(config)
    cache.set(key, data, CACHE_SECONDS)
    return data
