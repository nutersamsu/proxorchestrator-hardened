"""Backups / restore / storage content: parsing and strict validation."""

import re
from datetime import datetime
from datetime import timezone as dt_timezone

from django.utils import timezone

VOLID_RE = re.compile(r"^(?P<storage>[A-Za-z][A-Za-z0-9._-]{0,63}):(?P<path>[A-Za-z0-9][A-Za-z0-9._/+-]{0,250})$")
STORAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
BACKUP_NAME_RE = re.compile(
    r"vzdump-(?P<type>qemu|lxc)-(?P<vmid>\d+)-(?P<date>\d{4}_\d{2}_\d{2}-\d{2}_\d{2}_\d{2})"
)
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

MODES = [("snapshot", "Snapshot (no downtime)"), ("suspend", "Suspend"), ("stop", "Stop")]
COMPRESS = [("zstd", "ZSTD (fast and good)"), ("lzo", "LZO (fastest)"), ("gzip", "GZIP (good)"),
            ("0", "None")]
CONTENT_LABELS = {
    "backup": "Backups", "iso": "ISO images", "vztmpl": "CT templates", "images": "VM disks",
    "rootdir": "CT volumes", "snippets": "Snippets", "import": "Import",
}
# Job keys that are passed on when a scheduled job is run by hand.
JOB_RUN_KEYS = ("vmid", "all", "exclude", "pool", "storage", "mode", "compress", "mailto",
                "mailnotification", "notes-template", "protected", "remove", "zstd", "bwlimit",
                "ionice", "pigz", "fleecing", "pbs-change-detection-mode", "performance")


class BackupError(ValueError):
    pass


def valid_volid(volid):
    m = VOLID_RE.match(volid or "")
    if not m or ".." in volid or "//" in volid:
        return None
    return m.group("storage")


def valid_storage(name):
    return bool(name) and bool(STORAGE_RE.match(name))


def _ts(value):
    try:
        return timezone.localtime(datetime.fromtimestamp(int(value), tz=dt_timezone.utc))
    except (TypeError, ValueError, OSError):
        return None


def fmt_bytes(b):
    b = float(b or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if b < 1024 or unit == "TiB":
            return f"{b:.0f} {unit}" if unit == "B" else f"{b:.2f} {unit}"
        b /= 1024


def describe_volume(item, guests=None):
    """Decorate a storage content item for the templates."""
    guests = guests or {}
    volid = item.get("volid", "")
    name = volid.split(":", 1)[-1].split("/")[-1]
    m = BACKUP_NAME_RE.search(name)
    vmid = item.get("vmid") or (int(m.group("vmid")) if m else None)
    subtype = item.get("subtype") or (m.group("type") if m else "")
    guest = guests.get(int(vmid)) if vmid else None
    return {
        **item,
        "name": name,
        "storage": volid.split(":", 1)[0],
        "vmid": vmid,
        "subtype": subtype,
        "guest_name": guest.get("name") if guest else "",
        "guest_exists": bool(guest and guest.get("type") == subtype) if subtype else bool(guest),
        "date": _ts(item.get("ctime")),
        "size_h": fmt_bytes(item.get("size")),
        "protected": bool(item.get("protected")),
        "notes": item.get("notes", ""),
        "verified": (item.get("verification") or {}).get("state", ""),
    }


def describe_job(job):
    sel = "All guests" if str(job.get("all", "0")) == "1" else ""
    if job.get("vmid"):
        sel = "VMs/CTs " + ", ".join(str(job["vmid"]).split(","))
    if job.get("pool"):
        sel = f"Pool {job['pool']}"
    if job.get("exclude"):
        sel += f" (except {job['exclude']})"
    prune = job.get("prune-backups") or {}
    if isinstance(prune, str):
        prune = dict(p.split("=", 1) for p in prune.split(",") if "=" in p)
    return {
        **job,
        "selection": sel or "—",
        "next": _ts(job.get("next-run")),
        "retention": ", ".join(f"{k}={v}" for k, v in sorted(prune.items())) or "storage default",
        "enabled_b": str(job.get("enabled", "1")) == "1",
        "has_script": bool(job.get("script")),
    }


def job_run_params(job):
    """vzdump parameters for running a scheduled job now (as the PVE UI does).

    The job hook 'script' is dropped: Proxmox only lets root@pam set it.
    """
    params = {k: job[k] for k in JOB_RUN_KEYS if k in job and job[k] not in (None, "")}
    prune = job.get("prune-backups")
    if isinstance(prune, dict) and prune:
        params["prune-backups"] = ",".join(f"{k}={v}" for k, v in sorted(prune.items()))
    elif isinstance(prune, str) and prune:
        params["prune-backups"] = prune
    return params


def parse_backup_form(post, guests, backup_storages):
    vmids = []
    for raw in post.getlist("vmid") if hasattr(post, "getlist") else post.get("vmid", []):
        if not str(raw).isdigit() or int(raw) not in guests:
            raise BackupError(f"Unknown guest {raw!r}.")
        vmids.append(int(raw))
    if not vmids:
        raise BackupError("Select at least one VM or container.")
    storage = post.get("storage", "")
    if storage not in backup_storages:
        raise BackupError("Choose a storage that accepts backups.")
    mode = post.get("mode", "snapshot")
    if mode not in dict(MODES):
        raise BackupError("Unknown backup mode.")
    compress = post.get("compress", "zstd")
    if compress not in dict(COMPRESS):
        raise BackupError("Unknown compression.")
    notes = (post.get("notes") or "").strip()
    if len(notes) > 1024 or any(c in notes for c in "\r\n\x00"):
        raise BackupError("Notes: one line, up to 1024 characters.")
    params = {"vmid": ",".join(str(v) for v in sorted(set(vmids))), "storage": storage,
              "mode": mode, "compress": compress}
    if notes:
        params["notes-template"] = notes
    if post.get("protected") == "1":
        params["protected"] = 1
    return params


def parse_restore_form(post, kind, existing_vmids, source_vmid):
    raw = (post.get("target_vmid") or "").strip()
    if not raw.isdigit() or not (100 <= int(raw) <= 999999999):
        raise BackupError("Target ID must be a number from 100 to 999999999.")
    vmid = int(raw)
    exists = vmid in existing_vmids
    force = False
    if exists:
        if post.get("overwrite") != "1":
            raise BackupError(f"ID {vmid} is in use. Tick “overwrite” to replace it, or choose another ID.")
        if (post.get("confirm_overwrite") or "").strip() != str(vmid):
            raise BackupError(f"Type {vmid} to confirm that the existing guest will be replaced.")
        force = True
    storage = (post.get("storage") or "").strip()
    if storage and not valid_storage(storage):
        raise BackupError("Invalid target storage.")
    opts = {"vmid": vmid, "storage": storage or None, "force": force,
            "unique": post.get("unique") == "1", "start": post.get("start") == "1"}
    if kind == "lxc":
        opts["unprivileged"] = post.get("unprivileged") == "1"
    return opts


def summarize_config(text):
    """Pick the interesting lines of a guest config stored in a backup."""
    keep = re.compile(r"^(name|hostname|memory|cores|sockets|ostype|arch|net\d+|scsi\d+|virtio\d+|"
                      r"sata\d+|ide\d+|rootfs|mp\d+|efidisk0|tpmstate0|bios|unprivileged|"
                      r"swap|machine|agent|onboot)\s*:")
    lines = []
    for line in (text or "").splitlines():
        if line.startswith("["):  # snapshot sections
            break
        if keep.match(line):
            lines.append(line.strip())
    return lines
