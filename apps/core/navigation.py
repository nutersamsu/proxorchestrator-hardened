"""Sidebar of the Nexus shell: the sections of the Stitch design, pointing only at real pages.

Each item: label, url_name, icon (Font Awesome class), staff_only and ``match`` — prefixes of
``request.resolver_match.url_name`` that mark the item active (inner pages such as a VM's
detail or "New VM" light up their section). The first item that matches wins.
"""

from django.utils.translation import gettext_lazy as _

_VM_PAGES = ("inventory", "vm_detail", "vm_console", "vm_delete", "vm_rename", "vm_update",
             "vm_clone", "vm_disk", "vm_iso", "vm_cdrom", "vm_nic", "vm_networks", "vm_options",
             "vm_cloudinit", "vm_agent", "vm_convert", "vm_snapshot", "vm_action", "vm_row",
             "vm_ip", "check_vmid", "vmcreator_")
_LXC_PAGES = ("lxc_list", "lxc_stats", "lxc_console", "lxc_detail", "lxc_action", "lxc_delete",
              "lxc_update", "lxc_mountpoint", "lxc_volume", "lxc_convert", "lxc_networks",
              "lxc_nic", "lxc_row", "lxc_ip", "lxc_create", "lxc_template", "lxc_configure",
              "lxc_progress", "lxc_job", "lxc_cancel", "lxc_clone", "lxc_snapshot")


def _item(label, url_name, icon, match=(), staff_only=False):
    return {"label": label, "url_name": url_name, "icon": icon,
            "match": tuple(match) or (url_name,), "staff_only": staff_only}


NAV = [
    {"label": _("Datacenter & Cluster"), "items": [
        _item(_("Dashboard"), "dashboard", "fa-gauge-high", ("dashboard",)),
        _item(_("Nodes & Health"), "node_page", "fa-server", ("node_",), staff_only=True),
        _item(_("VMs & Guests"), "inventory", "fa-display", _VM_PAGES),
        _item(_("LXC & Containers"), "lxc_list", "fa-cube", _LXC_PAGES),
    ]},
    {"label": _("Storage & Backups"), "items": [
        _item(_("Storage Pools"), "datastore_list", "fa-database", ("datastore_",)),
        _item(_("Backup Jobs & Restore"), "backups_index", "fa-clock-rotate-left",
              ("backup", "guest_backup", "volume_delete")),
        _item(_("Export & Import"), "export_index", "fa-file-export",
              ("export_", "px_", "lxc_export_", "lxc_px_")),
        _item(_("Import files"), "storage_management", "fa-hard-drive", ("storage_",)),
    ]},
    {"label": _("Cyber Defense"), "items": [
        _item(_("Firewall & Rules"), "firewall_index", "fa-shield-halved", ("firewall_",)),
        _item(_("ACME TLS Certs"), "cert_settings", "fa-certificate", ("cert_", "acme_")),
    ]},
    {"label": _("Tools & Automation"), "items": [
        _item(_("LXC Store"), "lxc_community_scripts", "fa-store", ("lxc_community_scripts",)),
        _item(_("VM Marketplace"), "vm_community_scripts", "fa-diagram-project", ("vm_community_scripts",)),
        _item(_("Import Disk Wizard"), "importer_upload", "fa-file-import", ("importer_",)),
        _item(_("Setup Wizard"), "wizard_index", "fa-wand-magic-sparkles", ("wizard_",), staff_only=True),
    ]},
    {"label": _("System & IAM"), "items": [
        _item(_("Permissions & API"), "pveaccess_page", "fa-key", ("pveaccess_",), staff_only=True),
        _item(_("Task History & Logs"), "task_list", "fa-list-check", ("task_",)),
        _item(_("Auth & MFA"), "auth_settings", "fa-user-shield", ("auth_settings", "mfa_")),
        _item(_("Users"), "user_list", "fa-users", ("user_", "change_own_password")),
        _item(_("Proxmox"), "proxmox_settings", "fa-sliders", ("proxmox_settings",)),
        _item(_("Email"), "email_settings", "fa-envelope", ("email_settings",)),
    ]},
]


def sections_for(user, url_name):
    """Sections visible to ``user`` (staff-only items dropped), with ``active`` set on the
    first item whose prefixes match ``url_name``. Empty sections are left out."""
    url_name = url_name or ""
    is_staff = bool(getattr(user, "is_staff", False))
    found = False
    sections = []
    for section in NAV:
        items = []
        for item in section["items"]:
            if item["staff_only"] and not is_staff:
                continue
            active = not found and any(url_name.startswith(m) for m in item["match"])
            found = found or active
            items.append({**item, "active": active})
        if items:
            sections.append({"label": section["label"], "items": items})
    return sections
