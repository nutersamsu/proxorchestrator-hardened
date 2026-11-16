"""VM Options / Cloud-Init / extra hardware: parsing and strict validation.

Pure functions (no HTTP, no API) so they are easy to test. Every value that
goes to Proxmox is checked against a whitelist or a strict pattern first.
"""

import ipaddress
import re
from urllib.parse import quote
from urllib.parse import unquote

OSTYPES = [
    ("l26", "Linux 2.6 - 6.x kernel"),
    ("l24", "Linux 2.4 kernel"),
    ("win11", "Windows 11 / 2022 / 2025"),
    ("win10", "Windows 10 / 2016 / 2019"),
    ("win8", "Windows 8 / 2012 / 2012r2"),
    ("win7", "Windows 7 / 2008r2"),
    ("wvista", "Windows Vista / 2008"),
    ("w2k8", "Windows 2008"),
    ("w2k3", "Windows 2003"),
    ("w2k", "Windows 2000"),
    ("wxp", "Windows XP"),
    ("solaris", "Solaris"),
    ("other", "Other"),
]
OSTYPE_KEYS = {k for k, _ in OSTYPES}

VGA_TYPES = [
    ("std", "Standard VGA"), ("virtio", "VirtIO-GPU"), ("virtio-gl", "VirGL GPU"),
    ("qxl", "SPICE"), ("qxl2", "SPICE dual monitor"), ("qxl3", "SPICE three monitors"),
    ("qxl4", "SPICE four monitors"), ("vmware", "VMware compatible"), ("cirrus", "Cirrus Logic"),
    ("serial0", "Serial terminal 0"), ("serial1", "Serial terminal 1"),
    ("serial2", "Serial terminal 2"), ("serial3", "Serial terminal 3"), ("none", "None"),
]
VGA_KEYS = {k for k, _ in VGA_TYPES}

SCSIHW = [
    ("virtio-scsi-single", "VirtIO SCSI single"), ("virtio-scsi-pci", "VirtIO SCSI"),
    ("lsi", "LSI 53C895A"), ("lsi53c810", "LSI 53C810"), ("megasas", "MegaRAID SAS 8708EM2"),
    ("pvscsi", "VMware PVSCSI"),
]
SCSIHW_KEYS = {k for k, _ in SCSIHW}

HOTPLUG_ITEMS = ("disk", "network", "usb", "memory", "cpu", "cloudinit")
DEFAULT_HOTPLUG = "network,disk,usb"

CITYPES = [("", "Default"), ("nocloud", "NoCloud"), ("configdrive2", "ConfigDrive2"),
           ("opennebula", "OpenNebula")]
CITYPE_KEYS = {k for k, _ in CITYPES}

TAG_RE = re.compile(r"^[a-z0-9_][a-z0-9_+.-]*$", re.I)
CIUSER_RE = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$", re.I)
SSHKEY_RE = re.compile(r"^(ssh-(rsa|ed25519|dss)|ecdsa-sha2-nistp(256|384|521)|sk-(ssh-ed25519|ecdsa-sha2-nistp256)@openssh\.com) [A-Za-z0-9+/]{32,}={0,3}( [^\x00-\x1f\x7f]{0,200})?$")
STORAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
DISK_KEY_RE = re.compile(r"^(scsi([0-9]|[12][0-9]|30)|virtio([0-9]|1[0-5])|sata[0-5]|ide[0-3]|efidisk0|tpmstate0|unused[0-9]+)$")
CT_VOLUME_RE = re.compile(r"^(rootfs|mp([0-9]|[1-9][0-9]|2[0-4][0-9]|25[0-5]))$")

OTHER_HW_RE = re.compile(
    r"^(usb\d+|hostpci\d+|serial\d+|parallel\d+|audio\d+|rng\d+|watchdog|virtiofs\d+|"
    r"ivshmem|machine|scsihw|vga|args|affinity|vmgenid|smbios1)$"
)


class OptionError(ValueError):
    pass


def _bool(raw, key, default):
    v = raw.get(key)
    if v is None or v == "":
        return default
    return str(v) in ("1", "true")


def _kv(value):
    """'enabled=1,fstrim_cloned_disks=1' -> dict (first bare item as '_')."""
    out = {}
    for part in str(value or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        else:
            out.setdefault("_", part)
    return out


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

def build_options(raw):
    agent = _kv(raw.get("agent", ""))
    agent_enabled = agent.get("enabled", agent.get("_", "0")) == "1"
    startup = _kv(raw.get("startup", ""))
    hotplug = str(raw.get("hotplug", DEFAULT_HOTPLUG))
    hotplug_set = set() if hotplug in ("0", "") else (
        set(HOTPLUG_ITEMS) if hotplug == "1" else {h.strip() for h in hotplug.split(",")}
    )
    vga = _kv(raw.get("vga", ""))
    tags = [t for t in re.split(r"[;, ]+", str(raw.get("tags", ""))) if t]
    return {
        "opt_protection": _bool(raw, "protection", False),
        "opt_startup_order": startup.get("order", ""),
        "opt_startup_up": startup.get("up", ""),
        "opt_startup_down": startup.get("down", ""),
        "opt_startup_raw": raw.get("startup", ""),
        "opt_ostype": raw.get("ostype", "other"),
        "opt_agent": agent_enabled,
        "opt_agent_fstrim": agent.get("fstrim_cloned_disks", "0") == "1",
        "opt_tablet": _bool(raw, "tablet", True),
        "opt_acpi": _bool(raw, "acpi", True),
        "opt_kvm": _bool(raw, "kvm", True),
        "opt_localtime": _bool(raw, "localtime", False),
        "opt_freeze": _bool(raw, "freeze", False),
        "opt_hotplug": sorted(hotplug_set),
        "opt_hotplug_text": ", ".join(sorted(hotplug_set)) or "Disabled",
        "opt_tags": tags,
        "opt_tags_text": "; ".join(tags),
        "opt_vga": vga.get("type", vga.get("_", "std")) if raw.get("vga") else "std",
        "opt_vga_memory": vga.get("memory", ""),
        "opt_scsihw": raw.get("scsihw", "lsi"),
        "opt_machine": raw.get("machine", ""),
    }


def _int_field(post, name, lo, hi, label):
    raw = (post.get(name) or "").strip()
    if raw == "":
        return None
    if not raw.isdigit() or not (lo <= int(raw) <= hi):
        raise OptionError(f"{label} must be a number between {lo} and {hi}.")
    return int(raw)


def parse_options_form(post):
    """Return (kwargs, delete_keys) for PUT /qemu/{vmid}/config."""
    kwargs, delete = {}, []

    for key in ("protection", "tablet", "acpi", "kvm", "localtime", "freeze"):
        kwargs[key] = 1 if post.get(key) == "1" else 0

    ostype = post.get("ostype", "")
    if ostype not in OSTYPE_KEYS:
        raise OptionError("Unknown OS type.")
    kwargs["ostype"] = ostype

    order = _int_field(post, "startup_order", 0, 9999, "Start order")
    up = _int_field(post, "startup_up", 0, 86400, "Startup delay")
    down = _int_field(post, "startup_down", 0, 86400, "Shutdown timeout")
    parts = [f"{k}={v}" for k, v in (("order", order), ("up", up), ("down", down)) if v is not None]
    if parts:
        kwargs["startup"] = ",".join(parts)
    else:
        delete.append("startup")

    agent = "enabled=1" if post.get("agent") == "1" else "enabled=0"
    if post.get("agent") == "1" and post.get("agent_fstrim") == "1":
        agent += ",fstrim_cloned_disks=1"
    kwargs["agent"] = agent

    hot = [h for h in HOTPLUG_ITEMS if post.get(f"hotplug_{h}") == "1"]
    kwargs["hotplug"] = ",".join(hot) if hot else "0"

    tags = [t for t in re.split(r"[;, ]+", post.get("tags", "") or "") if t]
    for t in tags:
        if not TAG_RE.match(t) or len(t) > 64:
            raise OptionError(f"Invalid tag: {t!r} (letters, digits, _ + . - only).")
    if tags:
        kwargs["tags"] = ";".join(dict.fromkeys(t.lower() for t in tags))
    else:
        delete.append("tags")

    vga = post.get("vga", "std")
    if vga not in VGA_KEYS:
        raise OptionError("Unknown display type.")
    vga_mem = _int_field(post, "vga_memory", 4, 512, "Display memory (MiB)")
    if vga == "std" and vga_mem is None:
        delete.append("vga")
    else:
        kwargs["vga"] = vga + (f",memory={vga_mem}" if vga_mem is not None else "")

    scsihw = post.get("scsihw", "")
    if scsihw not in SCSIHW_KEYS:
        raise OptionError("Unknown SCSI controller.")
    kwargs["scsihw"] = scsihw

    return kwargs, delete


# PVE defaults for keys that are absent from the config file.
CONFIG_DEFAULTS = {
    "tablet": "1", "acpi": "1", "kvm": "1", "localtime": "0", "freeze": "0", "protection": "0",
    "hotplug": DEFAULT_HOTPLUG, "scsihw": "lsi", "ostype": "other", "agent": "enabled=0",
    "onboot": "0", "cmode": "tty", "tty": "2",
}


def _norm(key, value):
    value = "" if value is None else str(value)
    if key == "agent":
        kv = _kv(value)
        enabled = kv.get("enabled", kv.get("_", "0"))
        extra = ",".join(f"{k}={v}" for k, v in sorted(kv.items()) if k not in ("enabled", "_"))
        return f"enabled={enabled}" + (f",{extra}" if extra else "")
    if key == "hotplug":
        if value == "1":
            return ",".join(sorted(HOTPLUG_ITEMS))
        return ",".join(sorted(v for v in value.split(",") if v)) if value != "0" else "0"
    if key == "tags":
        return ";".join(t for t in re.split(r"[;, ]+", value) if t)
    return value


def only_changes(current, kwargs, delete):
    """Drop values equal to the current config and deletes of absent keys.

    Sending only what changed matters: some keys (e.g. 'startup', 'hookscript')
    need privileges the token does not have, even when the value is unchanged.
    """
    changed = {}
    for k, v in kwargs.items():
        cur = current.get(k, CONFIG_DEFAULTS.get(k))
        if _norm(k, cur) != _norm(k, v):
            changed[k] = v
    dels = [k for k in delete if k in current]
    return changed, dels


def other_hardware(raw):
    """Devices the app does not edit, shown read-only (as in PVE Hardware)."""
    return [{"key": k, "value": str(v)} for k, v in sorted(raw.items()) if OTHER_HW_RE.match(k)]


# ---------------------------------------------------------------------------
# Cloud-init
# ---------------------------------------------------------------------------

def find_cloudinit_drive(raw):
    for key, value in raw.items():
        if re.match(r"^(ide|sata|scsi)\d+$", key) and "cloudinit" in str(value):
            return key
    return None


def _parse_ipconfig(value):
    kv = _kv(value)
    ip, gw = kv.get("ip", ""), kv.get("gw", "")
    ip6, gw6 = kv.get("ip6", ""), kv.get("gw6", "")
    mode4 = "dhcp" if ip == "dhcp" else ("static" if ip else "none")
    mode6 = ip6 if ip6 in ("dhcp", "auto") else ("static" if ip6 else "none")
    return {
        "mode4": mode4, "ip4": ip if mode4 == "static" else "", "gw4": gw,
        "mode6": mode6, "ip6": ip6 if mode6 == "static" else "", "gw6": gw6,
    }


def net_keys(raw):
    return sorted((k for k in raw if re.match(r"^net\d+$", k)), key=lambda k: int(k[3:]))


def cloudinit_fields(raw):
    return {
        "drive": find_cloudinit_drive(raw),
        "ciuser": raw.get("ciuser", ""),
        "password_set": bool(raw.get("cipassword")),
        "sshkeys": unquote(raw.get("sshkeys", "")).strip(),
        "nameserver": raw.get("nameserver", ""),
        "searchdomain": raw.get("searchdomain", ""),
        "citype": raw.get("citype", ""),
        "ciupgrade": _bool(raw, "ciupgrade", True),
        "interfaces": [
            {"net": n, "idx": n[3:], **_parse_ipconfig(raw.get(f"ipconfig{n[3:]}", ""))}
            for n in net_keys(raw)
        ],
    }


def _cidr(value, version, label):
    try:
        iface = ipaddress.ip_interface(value)
    except ValueError:
        raise OptionError(f"{label}: {value!r} is not an address in CIDR form (e.g. 192.168.1.50/24).")
    if iface.version != version or "/" not in value:
        raise OptionError(f"{label}: use IPv{version} CIDR notation, e.g. "
                          f"{'192.168.1.50/24' if version == 4 else '2001:db8::5/64'}.")
    return value


def _ip(value, version, label):
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        raise OptionError(f"{label}: {value!r} is not a valid IP address.")
    if addr.version != version:
        raise OptionError(f"{label}: expected an IPv{version} address.")
    return value


def parse_cloudinit_form(post, raw):
    """Return (kwargs, delete_keys). Password is only changed when typed."""
    kwargs, delete = {}, []

    user = (post.get("ciuser") or "").strip()
    if user:
        if not CIUSER_RE.match(user):
            raise OptionError("User name: lowercase letters, digits, _ . - (max 32).")
        kwargs["ciuser"] = user
    else:
        delete.append("ciuser")

    password = post.get("cipassword") or ""
    if post.get("clear_password") == "1":
        delete.append("cipassword")
    elif password:
        if len(password) < 5 or len(password) > 256 or any(c in password for c in "\r\n"):
            raise OptionError("Password must be 5-256 characters on one line.")
        kwargs["cipassword"] = password

    keys = [k.strip() for k in (post.get("sshkeys") or "").replace("\r", "").split("\n") if k.strip()]
    for k in keys:
        if not SSHKEY_RE.match(k):
            raise OptionError("SSH keys: one OpenSSH public key per line (ssh-ed25519 AAAA… comment).")
    if keys:
        kwargs["sshkeys"] = quote("\n".join(keys) + "\n", safe="")
    else:
        delete.append("sshkeys")

    servers = [s for s in re.split(r"[\s,]+", post.get("nameserver") or "") if s]
    for s in servers:
        try:
            ipaddress.ip_address(s)
        except ValueError:
            raise OptionError(f"DNS server {s!r} is not an IP address.")
    if servers:
        kwargs["nameserver"] = " ".join(servers)
    else:
        delete.append("nameserver")

    domains = [d for d in re.split(r"[\s,]+", post.get("searchdomain") or "") if d]
    for d in domains:
        if not DOMAIN_RE.match(d):
            raise OptionError(f"Search domain {d!r} is not a valid domain.")
    if domains:
        kwargs["searchdomain"] = " ".join(domains)
    else:
        delete.append("searchdomain")

    citype = post.get("citype", "")
    if citype not in CITYPE_KEYS:
        raise OptionError("Unknown cloud-init type.")
    if citype:
        kwargs["citype"] = citype
    else:
        delete.append("citype")

    kwargs["ciupgrade"] = 1 if post.get("ciupgrade") == "1" else 0

    for n in net_keys(raw):
        idx = n[3:]
        parts = []
        mode4 = post.get(f"mode4_{idx}", "none")
        if mode4 == "dhcp":
            parts.append("ip=dhcp")
        elif mode4 == "static":
            parts.append("ip=" + _cidr((post.get(f"ip4_{idx}") or "").strip(), 4, f"{n} IPv4"))
            gw = (post.get(f"gw4_{idx}") or "").strip()
            if gw:
                parts.append("gw=" + _ip(gw, 4, f"{n} gateway"))
        elif mode4 != "none":
            raise OptionError("Unknown IPv4 mode.")
        mode6 = post.get(f"mode6_{idx}", "none")
        if mode6 in ("dhcp", "auto"):
            parts.append(f"ip6={mode6}")
        elif mode6 == "static":
            parts.append("ip6=" + _cidr((post.get(f"ip6_{idx}") or "").strip(), 6, f"{n} IPv6"))
            gw6 = (post.get(f"gw6_{idx}") or "").strip()
            if gw6:
                parts.append("gw6=" + _ip(gw6, 6, f"{n} IPv6 gateway"))
        elif mode6 != "none":
            raise OptionError("Unknown IPv6 mode.")
        if parts:
            kwargs[f"ipconfig{idx}"] = ",".join(parts)
        else:
            delete.append(f"ipconfig{idx}")

    return kwargs, delete


HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$", re.I)


def parse_ct_dns_form(post):
    """Container DNS tab: hostname, DNS servers, search domain."""
    kwargs, delete = {}, []
    hostname = (post.get("hostname") or "").strip()
    if not HOSTNAME_RE.match(hostname):
        raise OptionError("Host name: letters, digits and '-' (dots between labels).")
    kwargs["hostname"] = hostname
    servers = [s for s in re.split(r"[\s,]+", post.get("nameserver") or "") if s]
    for s in servers:
        try:
            ipaddress.ip_address(s)
        except ValueError:
            raise OptionError(f"DNS server {s!r} is not an IP address.")
    if servers:
        kwargs["nameserver"] = " ".join(servers)
    else:
        delete.append("nameserver")
    domains = [d for d in re.split(r"[\s,]+", post.get("searchdomain") or "") if d]
    for d in domains:
        if not DOMAIN_RE.match(d):
            raise OptionError(f"Search domain {d!r} is not a valid domain.")
    if domains:
        kwargs["searchdomain"] = " ".join(domains)
    else:
        delete.append("searchdomain")
    return kwargs, delete


def valid_storage(name):
    return bool(name) and bool(STORAGE_RE.match(name))
