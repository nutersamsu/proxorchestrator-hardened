import logging
import os
import re

from django import forms
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy

logger = logging.getLogger(__name__)


def sanitize_vm_name(name):
    """Convert a filename stem into a valid Proxmox VM name (DNS hostname).

    Proxmox requires: letters, digits, and hyphens only; must not start/end
    with a hyphen; max 63 characters.
    """
    # Replace underscores, dots, spaces with hyphens
    name = re.sub(r"[._\s]+", "-", name)
    # Strip anything that isn't alphanumeric or hyphen
    name = re.sub(r"[^a-zA-Z0-9-]", "", name)
    # Collapse multiple hyphens
    name = re.sub(r"-{2,}", "-", name)
    # Strip leading/trailing hyphens
    name = name.strip("-")
    # Truncate to 63 chars (DNS label limit)
    name = name[:63].rstrip("-")
    return name or "imported-vm"


vm_name_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$",
    message="VM name must contain only letters, numbers, and hyphens, "
            "and must not start or end with a hyphen (max 63 characters).",
)

ALLOWED_EXTENSIONS = {".qcow2", ".vmdk", ".vhd", ".vhdx", ".raw", ".img", ".ova"}

CPU_TYPE_CHOICES = [
    ("host", gettext_lazy("host")),
    ("max", gettext_lazy("max")),
    ("kvm64", gettext_lazy("kvm64")),
    ("x86-64-v2", "x86-64-v2"),
    ("x86-64-v2-AES", gettext_lazy("x86-64-v2-AES")),
    ("x86-64-v3", "x86-64-v3"),
    ("x86-64-v4", "x86-64-v4"),
    ("qemu64", gettext_lazy("qemu64")),
    ("Nehalem", gettext_lazy("Nehalem")),
    ("Westmere", gettext_lazy("Westmere")),
    ("SandyBridge", gettext_lazy("SandyBridge")),
    ("IvyBridge", gettext_lazy("IvyBridge")),
    ("Haswell", gettext_lazy("Haswell")),
    ("Broadwell", gettext_lazy("Broadwell")),
    ("Skylake-Client", gettext_lazy("Skylake-Client")),
    ("Skylake-Server", gettext_lazy("Skylake-Server")),
    ("Cascadelake-Server", gettext_lazy("Cascadelake-Server")),
    ("Icelake-Server", gettext_lazy("Icelake-Server")),
    ("EPYC", gettext_lazy("EPYC")),
    ("EPYC-v2", gettext_lazy("EPYC-v2")),
    ("EPYC-v3", gettext_lazy("EPYC-v3")),
    ("EPYC-v4", gettext_lazy("EPYC-v4")),
    ("EPYC-Rome", gettext_lazy("EPYC-Rome")),
    ("EPYC-Milan", gettext_lazy("EPYC-Milan")),
]

OS_TYPE_CHOICES = [
    ("l26", gettext_lazy("Linux 6.x / 5.x")),
    ("l24", gettext_lazy("Linux 4.x")),
    ("win11", gettext_lazy("Windows 11")),
    ("win10", gettext_lazy("Windows 10/2022")),
    ("win2k19", gettext_lazy("Windows 2019")),
    ("win2k8", gettext_lazy("Windows 2008/Vista")),
    ("other", gettext_lazy("Other")),
]

BIOS_CHOICES = [
    ("seabios", gettext_lazy("SeaBIOS (legacy)")),
    ("ovmf", gettext_lazy("UEFI (OVMF)")),
]

MACHINE_TYPE_CHOICES = [
    ("pc", gettext_lazy("i440FX (legacy)")),
    ("q35", gettext_lazy("Q35 (modern, PCIe)")),
]

DISK_BUS_CHOICES = [
    ("scsi", gettext_lazy("VirtIO-SCSI (recommended)")),
    ("virtio", gettext_lazy("VirtIO Block")),
    ("sata", gettext_lazy("SATA")),
    ("ide", gettext_lazy("IDE")),
]

DISK_CACHE_CHOICES = [
    ("none", gettext_lazy("No cache")),
    ("writeback", gettext_lazy("Write back")),
    ("writethrough", gettext_lazy("Write through")),
    ("directsync", gettext_lazy("Direct sync")),
    ("unsafe", gettext_lazy("Unsafe")),
]

NET_MODEL_CHOICES = [
    ("virtio", gettext_lazy("VirtIO (recommended)")),
    ("e1000", gettext_lazy("Intel E1000")),
    ("e1000e", gettext_lazy("Intel E1000e")),
    ("vmxnet3", gettext_lazy("VMware vmxnet3")),
    ("rtl8139", gettext_lazy("Realtek RTL8139")),
]

VGA_TYPE_CHOICES = [
    ("std", gettext_lazy("Standard")),
    ("virtio", gettext_lazy("VirtIO")),
    ("vmware", gettext_lazy("VMware")),
    ("qxl", gettext_lazy("SPICE/QXL")),
    ("cirrus", gettext_lazy("Cirrus")),
    ("none", gettext_lazy("None")),
]


VMWARE_EXTENSIONS = {".ova", ".vmdk"}
HYPERV_EXTENSIONS = {".vhd", ".vhdx"}
KVM_EXTENSIONS = {".qcow2", ".raw", ".img"}


def detect_source_platform(filename):
    """Detect the source virtualisation platform from the filename extension.

    Returns 'vmware', 'hyperv', 'kvm', or None.
    """
    _, ext = os.path.splitext(filename.lower())
    if ext in VMWARE_EXTENSIONS:
        return "vmware"
    if ext in HYPERV_EXTENSIONS:
        return "hyperv"
    if ext in KVM_EXTENSIONS:
        return "kvm"
    return None


HARDWARE_PRESETS = {
    "Server OS": [
        {
            "key": "windows-server",
            "label": "Windows Server (2016/2019/2022)",
            "config": {
                "cpu_type": "host", "cores": 4, "sockets": 1,
                "memory_mb": 4096, "net_model": "e1000e", "disk_bus": "sata",
                "os_type": "win10", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "windows-desktop",
            "label": "Windows 10 / 11",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 4096, "net_model": "e1000e", "disk_bus": "sata",
                "os_type": "win10", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "linux-ubuntu",
            "label": "Linux — Ubuntu / Debian",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 2048, "net_model": "e1000", "disk_bus": "scsi",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": True, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "linux-rhel",
            "label": "Linux — RHEL / CentOS / Rocky",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 2048, "net_model": "e1000", "disk_bus": "scsi",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": True, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "linux-other",
            "label": "Linux — Other",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 2048, "net_model": "e1000", "disk_bus": "scsi",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": True, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "freebsd",
            "label": "FreeBSD",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 2048, "net_model": "e1000", "disk_bus": "sata",
                "os_type": "other", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
    ],
    "Appliances": [
        {
            "key": "forgedlabs-pro",
            "label": "BackupAssure — Pro",
            "config": {
                "cpu_type": "host", "cores": 4, "sockets": 1,
                "memory_mb": 12288, "net_model": "virtio", "disk_bus": "scsi",
                "os_type": "l26", "machine": "q35", "bios": "ovmf",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": True, "disk_discard": True, "disk_ssd": True,
                "ballooning": False, "qemu_agent": True, "efi_disk": True,
            },
        },
        {
            "key": "forgedlabs-standard",
            "label": "BackupAssure — Standard",
            "config": {
                "cpu_type": "host", "cores": 4, "sockets": 1,
                "memory_mb": 12288, "net_model": "virtio", "disk_bus": "scsi",
                "os_type": "l26", "machine": "q35", "bios": "ovmf",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": True, "disk_discard": True, "disk_ssd": True,
                "ballooning": False, "qemu_agent": True, "efi_disk": True,
            },
        },
        {
            "key": "cisco-8000v",
            "label": "Cisco — Catalyst 8000V / CSR 1000v",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 4096, "net_model": "virtio", "disk_bus": "scsi",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                "serial_port": True,
            },
        },
        {
            "key": "cisco-expressway",
            "label": "Cisco — Expressway / VCS",
            "config": {
                "cpu_type": "qemu64", "cores": 4, "sockets": 1,
                "memory_mb": 6144, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                "serial_port": True,
            },
        },
        {
            "key": "cisco-cucm",
            "label": "Cisco — CUCM / UCM",
            "config": {
                "cpu_type": "host", "cores": 4, "sockets": 1,
                "memory_mb": 8192, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                "serial_port": True,
            },
        },
        {
            "key": "cisco-ise",
            "label": "Cisco — ISE",
            "sizes": [
                {"key": "cisco-ise-xs", "label": "Extra Small — Lab (8 vCPU / 32 GB)", "config": {
                    "cpu_type": "host", "cores": 8, "sockets": 1,
                    "memory_mb": 32768, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-small-3615", "label": "Small — SNS 3615 (16 vCPU / 32 GB)", "config": {
                    "cpu_type": "host", "cores": 16, "sockets": 1,
                    "memory_mb": 32768, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-medium-3655", "label": "Medium — SNS 3655 (24 vCPU / 96 GB)", "config": {
                    "cpu_type": "host", "cores": 24, "sockets": 1,
                    "memory_mb": 98304, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-large-3695", "label": "Large — SNS 3695 (24 vCPU / 256 GB)", "config": {
                    "cpu_type": "host", "cores": 24, "sockets": 1,
                    "memory_mb": 262144, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-small-3715", "label": "Small — SNS 3715 (24 vCPU / 32 GB)", "config": {
                    "cpu_type": "host", "cores": 24, "sockets": 1,
                    "memory_mb": 32768, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-medium-3755", "label": "Medium — SNS 3755 (40 vCPU / 96 GB)", "config": {
                    "cpu_type": "host", "cores": 40, "sockets": 1,
                    "memory_mb": 98304, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-large-3795", "label": "Large — SNS 3795 (40 vCPU / 256 GB)", "config": {
                    "cpu_type": "host", "cores": 40, "sockets": 1,
                    "memory_mb": 262144, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-small-3815", "label": "Small — SNS 3815 (32 vCPU / 64 GB)", "config": {
                    "cpu_type": "host", "cores": 32, "sockets": 1,
                    "memory_mb": 65536, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-medium-3855", "label": "Medium — SNS 3855 (48 vCPU / 128 GB)", "config": {
                    "cpu_type": "host", "cores": 48, "sockets": 1,
                    "memory_mb": 131072, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
                {"key": "cisco-ise-large-3895", "label": "Large — SNS 3895 (48 vCPU / 256 GB)", "config": {
                    "cpu_type": "host", "cores": 48, "sockets": 1,
                    "memory_mb": 262144, "net_model": "virtio", "disk_bus": "ide",
                    "os_type": "l26", "machine": "pc", "bios": "seabios",
                    "vga_type": "std", "disk_cache": "none",
                    "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                    "serial_port": True,
                }},
            ],
        },
        {
            "key": "cisco-fmc",
            "label": "Cisco — FMC / FTD",
            "config": {
                "cpu_type": "host", "cores": 4, "sockets": 1,
                "memory_mb": 32768, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                "serial_port": True,
            },
        },
        {
            "key": "cisco-other",
            "label": "Cisco — Other",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 4096, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
                "serial_port": True,
            },
        },
        {
            "key": "aruba-clearpass",
            "label": "Aruba — ClearPass",
            "config": {
                "cpu_type": "host", "cores": 4, "sockets": 1,
                "memory_mb": 8192, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "aruba-other",
            "label": "Aruba — Other",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 4096, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "paloalto-firewall",
            "label": "Palo Alto — Firewall",
            "config": {
                "cpu_type": "host", "cores": 4, "sockets": 1,
                "memory_mb": 6656, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "fortinet-fortigate",
            "label": "Fortinet — FortiGate",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 2048, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "sophos-firewall",
            "label": "Sophos — Firewall",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 4096, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
        {
            "key": "appliance-other",
            "label": "Appliance — Other",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 4096, "net_model": "e1000", "disk_bus": "ide",
                "os_type": "l26", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
    ],
    "Other": [
        {
            "key": "other",
            "label": "Other / Unknown",
            "config": {
                "cpu_type": "host", "cores": 2, "sockets": 1,
                "memory_mb": 2048, "net_model": "e1000", "disk_bus": "sata",
                "os_type": "other", "machine": "pc", "bios": "seabios",
                "vga_type": "std", "disk_cache": "none",
                "disk_iothread": False, "ballooning": False, "qemu_agent": False,
            },
        },
    ],
}


class UploadForm(forms.Form):
    """Disk image upload form."""

    disk_image = forms.FileField(
        label=gettext_lazy("Disk Image"),
        widget=forms.FileInput(
            attrs={
                "accept": ".qcow2,.vmdk,.vhd,.vhdx,.raw,.img,.ova",
            }
        ),
        help_text=gettext_lazy("Supported formats: qcow2, vmdk, vhd, vhdx, raw, img, ova"),
    )

    def clean_disk_image(self):
        f = self.cleaned_data["disk_image"]
        _name, ext = os.path.splitext(f.name.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                f"Unsupported file extension: {ext!r}. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        return f


class VMConfigForm(forms.Form):
    """Full VM configuration form for creating a Proxmox VM from an uploaded image."""

    # --- General ---
    vm_name = forms.CharField(
        max_length=63,
        label=gettext_lazy("VM Name"),
        validators=[vm_name_validator],
        widget=forms.TextInput(attrs={"placeholder": "my-server"}),
        help_text=gettext_lazy("Letters, numbers, and hyphens only."),
    )
    vmid = forms.IntegerField(
        required=False,
        label=gettext_lazy("VMID"),
        min_value=100,
        max_value=999999999,
        help_text=gettext_lazy("Leave blank to auto-assign from pool."),
    )
    node = forms.ChoiceField(
        label=gettext_lazy("Proxmox Node"),
        choices=[],
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label=gettext_lazy("Description"),
    )
    os_type = forms.ChoiceField(
        choices=OS_TYPE_CHOICES,
        label=gettext_lazy("OS Type"),
        initial="l26",
    )

    # --- Firmware ---
    machine = forms.ChoiceField(
        choices=MACHINE_TYPE_CHOICES,
        label=gettext_lazy("Machine Type"),
        initial="pc",
    )
    bios = forms.ChoiceField(
        choices=BIOS_CHOICES,
        label=gettext_lazy("BIOS Type"),
        initial="seabios",
    )
    efi_disk = forms.BooleanField(
        required=False,
        label=gettext_lazy("Add EFI Disk"),
        help_text=gettext_lazy("Required when using UEFI/OVMF."),
    )
    secure_boot_keys = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enroll Secure Boot Keys"),
    )
    tpm = forms.BooleanField(
        required=False,
        label=gettext_lazy("Add TPM 2.0 State Drive"),
    )
    start_on_boot = forms.BooleanField(
        required=False,
        label=gettext_lazy("Start on Boot"),
    )

    # --- CPU ---
    cpu_type = forms.ChoiceField(
        choices=CPU_TYPE_CHOICES,
        label=gettext_lazy("CPU Type"),
        initial="host",
    )
    sockets = forms.IntegerField(
        initial=1,
        label=gettext_lazy("CPU Sockets"),
        min_value=1,
        max_value=8,
    )
    cores = forms.IntegerField(
        initial=2,
        label=gettext_lazy("CPU Cores (per socket)"),
        min_value=1,
        max_value=256,
    )
    numa = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable NUMA"),
    )

    # --- Memory ---
    memory_mb = forms.IntegerField(
        initial=2048,
        label=gettext_lazy("Memory (MB)"),
        min_value=64,
    )
    ballooning = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable Memory Ballooning"),
        initial=False,
    )
    balloon_min_mb = forms.IntegerField(
        required=False,
        label=gettext_lazy("Balloon Minimum (MB)"),
        min_value=0,
        help_text=gettext_lazy("Minimum memory with ballooning enabled."),
    )

    # --- Primary Disk ---
    disk_bus = forms.ChoiceField(
        choices=DISK_BUS_CHOICES,
        label=gettext_lazy("Disk Bus / Controller"),
        initial="scsi",
    )
    storage_pool = forms.ChoiceField(
        label=gettext_lazy("Storage Pool"),
        choices=[],
    )
    disk_cache = forms.ChoiceField(
        choices=DISK_CACHE_CHOICES,
        label=gettext_lazy("Disk Cache Mode"),
        initial="none",
    )
    disk_iothread = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable I/O Thread"),
        initial=True,
        help_text=gettext_lazy("Recommended for VirtIO-SCSI."),
    )
    disk_discard = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable Discard (TRIM)"),
    )
    disk_ssd = forms.BooleanField(
        required=False,
        label=gettext_lazy("Emulate SSD"),
    )
    keep_converted_image = forms.BooleanField(
        required=False,
        initial=False,
        label=gettext_lazy("Keep the converted image on Proxmox for reuse"),
        help_text=gettext_lazy("Leaves a copy in the Proxmox temp directory (as large as the disk) "
                  "so it can be imported again from Storage. Off by default."),
    )

    # Extra disks (JSON array serialized by JS: [{storage, size_gb}, ...])
    extra_disks = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    # --- Network ---
    net_bridge = forms.ChoiceField(
        label=gettext_lazy("Network Bridge"),
        choices=[],
    )
    net_model = forms.ChoiceField(
        choices=NET_MODEL_CHOICES,
        label=gettext_lazy("Network Model"),
        initial="virtio",
    )
    net_vlan = forms.IntegerField(
        required=False,
        label=gettext_lazy("VLAN Tag"),
        min_value=1,
        max_value=4094,
        help_text=gettext_lazy("Leave blank for untagged."),
    )
    net_firewall = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable Proxmox Firewall"),
    )
    net_mac = forms.CharField(
        max_length=17,
        required=False,
        label=gettext_lazy("MAC Address"),
        help_text=gettext_lazy("Leave blank to auto-generate. Format: AA:BB:CC:DD:EE:FF"),
    )

    # --- Display ---
    vga_type = forms.ChoiceField(
        choices=VGA_TYPE_CHOICES,
        label=gettext_lazy("Display Type"),
        initial="std",
    )
    vga_memory = forms.IntegerField(
        required=False,
        initial=16,
        label=gettext_lazy("Display Memory (MB)"),
        min_value=4,
        max_value=512,
    )

    # --- Agent / Misc ---
    qemu_agent = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable QEMU Guest Agent"),
    )
    tablet = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable USB Tablet (for VNC pointer sync)"),
    )
    serial_port = forms.BooleanField(
        required=False,
        label=gettext_lazy("Add Serial Port (socket)"),
        help_text=gettext_lazy("Required for some appliances (e.g. Cisco Expressway install wizard)."),
    )
    protection = forms.BooleanField(
        required=False,
        label=gettext_lazy("Enable VM Protection (prevents accidental deletion)"),
    )
    start_after_import = forms.BooleanField(required=False)
    virtio_iso_ref = forms.CharField(required=False, max_length=500)
    ova_iso_storage = forms.CharField(required=False, max_length=200)

    # --- Cloud-Init ---
    cloud_init_enabled = forms.BooleanField(required=False)
    ci_storage = forms.ChoiceField(required=False, choices=[])
    ci_user = forms.CharField(required=False, max_length=100)
    ci_password = forms.CharField(required=False, max_length=200, widget=forms.PasswordInput(render_value=True))
    ci_ssh_keys = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    ci_ip_config = forms.ChoiceField(
        required=False,
        choices=[("dhcp", gettext_lazy("DHCP")), ("static", gettext_lazy("Static")), ("none", gettext_lazy("None"))],
        initial="dhcp",
    )
    ci_ip_address = forms.CharField(required=False, max_length=50, help_text="e.g. 192.168.1.100/24")
    ci_gateway = forms.CharField(required=False, max_length=50)
    ci_nameserver = forms.CharField(required=False, max_length=100)
    ci_search_domain = forms.CharField(required=False, max_length=200)
    ci_user_data = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 8}))

    def __init__(
        self,
        *args,
        node_choices=None,
        storage_choices=None,
        bridge_choices=None,
        config_defaults=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        if node_choices:
            self.fields["node"].choices = node_choices
        if storage_choices:
            self.fields["storage_pool"].choices = storage_choices
            self.fields["ci_storage"].choices = [("", "— same as primary —")] + list(storage_choices)
        if bridge_choices:
            self.fields["net_bridge"].choices = bridge_choices

        # Pre-fill defaults from ProxmoxConfig
        if config_defaults is not None:
            self.fields["cores"].initial = config_defaults.default_cores
            self.fields["memory_mb"].initial = config_defaults.default_memory_mb
            if config_defaults.default_node:
                self.fields["node"].initial = config_defaults.default_node
            if config_defaults.default_storage:
                self.fields["storage_pool"].initial = config_defaults.default_storage
            if config_defaults.default_bridge:
                self.fields["net_bridge"].initial = config_defaults.default_bridge
