import logging

from django import forms
from django.utils.translation import gettext_lazy

logger = logging.getLogger(__name__)


class Step1Form(forms.Form):
    """Step 1: Proxmox host address and ports."""

    host = forms.CharField(
        max_length=255,
        label=gettext_lazy("Proxmox Host"),
        help_text=gettext_lazy("Hostname or IP address of your Proxmox server."),
        widget=forms.TextInput(attrs={"placeholder": "192.168.1.10 or pve.example.com"}),
    )
    ssh_port = forms.IntegerField(
        initial=22,
        label=gettext_lazy("SSH Port"),
        min_value=1,
        max_value=65535,
        help_text=gettext_lazy("Default is 22."),
    )
    api_port = forms.IntegerField(
        initial=8006,
        label=gettext_lazy("Proxmox API Port"),
        min_value=1,
        max_value=65535,
        help_text=gettext_lazy("Default is 8006."),
    )


class Step2Form(forms.Form):
    """Step 2: Root password for one-time SSH key copy."""

    root_password = forms.CharField(
        label=gettext_lazy("Proxmox Root Password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text=gettext_lazy("Used once to copy the SSH key. Never stored."),
    )


class Step3Form(forms.Form):
    """Step 3: Proxmox API token credentials."""

    api_token_id = forms.CharField(
        max_length=255,
        label=gettext_lazy("API Token ID"),
        help_text=gettext_lazy("Format: user@realm!tokenid — e.g. root@pam!proxorchestrator"),
        widget=forms.TextInput(attrs={"placeholder": "root@pam!proxorchestrator"}),
    )
    api_token_secret = forms.CharField(
        max_length=255,
        label=gettext_lazy("API Token Secret"),
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )


class Step5Form(forms.Form):
    """Step 5: Default VM creation settings."""

    default_node = forms.ChoiceField(
        label=gettext_lazy("Default Proxmox Node"),
        choices=[],
    )
    default_storage = forms.ChoiceField(
        label=gettext_lazy("Default Storage Pool"),
        choices=[],
    )
    default_bridge = forms.ChoiceField(
        label=gettext_lazy("Default Network Bridge"),
        choices=[],
    )
    proxmox_temp_dir = forms.CharField(
        max_length=500,
        label=gettext_lazy("Proxmox Temp Directory"),
        initial="/var/tmp/proxorchestrator/",
        help_text=gettext_lazy("Temporary directory on the Proxmox host for disk image staging."),
    )
    default_cores = forms.IntegerField(
        initial=2,
        label=gettext_lazy("Default CPU Cores"),
        min_value=1,
        max_value=128,
    )
    default_memory_mb = forms.IntegerField(
        initial=2048,
        label=gettext_lazy("Default Memory (MB)"),
        min_value=256,
        help_text=gettext_lazy("Memory in megabytes."),
    )
    vmid_min = forms.IntegerField(
        initial=100,
        label=gettext_lazy("VMID Pool — Minimum"),
        min_value=100,
        help_text=gettext_lazy("Lowest VMID ProxOrchestrator will auto-assign."),
    )
    vmid_max = forms.IntegerField(
        initial=999,
        label=gettext_lazy("VMID Pool — Maximum"),
        min_value=101,
        help_text=gettext_lazy("Highest VMID ProxOrchestrator will auto-assign."),
    )
    virtio_iso = forms.CharField(
        max_length=500,
        required=False,
        label=gettext_lazy("VirtIO Windows Drivers ISO"),
        help_text=(
            gettext_lazy("Proxmox storage reference to the VirtIO driver ISO "
            "(e.g. data:iso/virtio-win-0.1.285.iso). "
            "Leave blank to disable automatic VirtIO ISO attachment.")
        ),
    )

    def __init__(self, *args, node_choices=None, storage_choices=None, bridge_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if node_choices:
            self.fields["default_node"].choices = node_choices
        if storage_choices:
            self.fields["default_storage"].choices = storage_choices
        if bridge_choices:
            self.fields["default_bridge"].choices = bridge_choices

    def clean(self):
        cleaned = super().clean()
        vmid_min = cleaned.get("vmid_min")
        vmid_max = cleaned.get("vmid_max")
        if vmid_min is not None and vmid_max is not None and vmid_min >= vmid_max:
            raise forms.ValidationError("VMID minimum must be less than VMID maximum.")
        return cleaned
