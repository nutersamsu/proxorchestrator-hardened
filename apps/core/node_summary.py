"""Proxmox node summary for the dashboard.

Mirrors the information of the PVE web UI "Summary" panel of a node (without
the RRD graphs) and adds hardware temperatures, which the PVE API does not
expose. Temperatures are read over the app's existing SSH connection straight
from /sys/class/hwmon, so nothing (lm-sensors etc.) has to be installed on the
host.
"""

import logging

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


def _pct(used, total):
    try:
        return round(100.0 * float(used) / float(total), 1) if total else 0.0
    except (TypeError, ValueError):
        return 0.0


def format_bytes(value):
    """Binary units like the PVE UI (GiB)."""
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
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "-"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    return f"{hours:02d}h {minutes:02d}m"


def build_summary(status):
    """Turn /nodes/{node}/status into template-friendly values."""
    mem = status.get("memory") or {}
    swap = status.get("swap") or {}
    rootfs = status.get("rootfs") or {}
    cpuinfo = status.get("cpuinfo") or {}
    boot = status.get("boot-info") or {}
    ksm = status.get("ksm") or {}
    kernel = status.get("current-kernel") or {}

    def usage(block):
        total = block.get("total") or 0
        used = block.get("used")
        if used is None and total:
            used = total - (block.get("free") or block.get("avail") or 0)
        used = used or 0
        return {
            "pct": _pct(used, total),
            "used": format_bytes(used),
            "total": format_bytes(total),
            "present": bool(total),
        }

    cpus = cpuinfo.get("cpus")
    sockets = cpuinfo.get("sockets")
    model = cpuinfo.get("model") or ""
    cpu_desc = model
    if cpus:
        cpu_desc = f"{cpus} x {model}" if model else f"{cpus} CPU(s)"
        if sockets:
            cpu_desc += f" ({sockets} Socket{'s' if int(sockets) != 1 else ''})"

    boot_mode = (boot.get("mode") or "").upper()
    if boot_mode == "EFI" and boot.get("secureboot"):
        boot_mode = "EFI (Secure Boot)"
    elif boot_mode == "LEGACY-BIOS":
        boot_mode = "Legacy BIOS"

    kversion = status.get("kversion") or ""
    if kernel.get("sysname") and kernel.get("release"):
        kversion = f"{kernel['sysname']} {kernel['release']} {kernel.get('version', '')}".strip()

    load = status.get("loadavg") or []
    return {
        "cpu_pct": _pct(status.get("cpu") or 0, 1),
        "cpus": cpus,
        "io_delay_pct": _pct(status.get("wait") or 0, 1),
        "loadavg": ", ".join(str(x) for x in load) if load else "-",
        "memory": usage(mem),
        "swap": usage(swap),
        "rootfs": usage(rootfs),
        "ksm_shared": format_bytes(ksm.get("shared") or 0),
        "cpu_desc": cpu_desc or "-",
        "cpu_mhz": cpuinfo.get("mhz"),
        "kernel": kversion or "-",
        "boot_mode": boot_mode or "-",
        "pveversion": status.get("pveversion") or "-",
        "uptime": format_uptime(status.get("uptime")),
    }


def get_node_summary(config, use_cache=True):
    """Return the context for the node summary card (cached briefly)."""
    node = config.default_node
    key = f"po:node-summary:{config.pk}:{node}"
    if use_cache:
        cached = cache.get(key)
        if cached is not None:
            return cached

    data = {"node": node, "summary": None, "error": None, "temps": [], "temps_error": None}
    try:
        status = config.get_api_client().get_node_status(node)
        data["summary"] = build_summary(status)
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
