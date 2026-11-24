"""Default values of the VM forms (Create VM and Import VM).

The defaults follow the Proxmox VE Administration Guide for Linux guests on
SSD/thin storage: memory ballooning on (the Proxmox UI default), discard and
SSD emulation on, QEMU guest agent on, VirtIO SCSI single with IO thread.
"""
from django.test import SimpleTestCase

from apps.importer.forms import HARDWARE_PRESETS, VMConfigForm
from apps.vmcreator.forms import VmCreateConfigForm

RECOMMENDED_ON = ("ballooning", "disk_discard", "disk_ssd", "qemu_agent", "disk_iothread")


class VmFormDefaultsTests(SimpleTestCase):
    def _assert_defaults(self, form):
        for name in RECOMMENDED_ON:
            with self.subTest(form=type(form).__name__, field=name):
                # The templates check the box from form.<field>.value(),
                # which for an unbound form is the field's initial value.
                self.assertTrue(form[name].value(), f"{name} should be on by default")
        self.assertEqual(form["disk_bus"].value(), "scsi")
        self.assertEqual(form["cpu_type"].value(), "host")
        self.assertEqual(form["net_model"].value(), "virtio")

    def test_create_vm_form_defaults(self):
        self._assert_defaults(VmCreateConfigForm())

    def test_import_vm_form_defaults(self):
        self._assert_defaults(VMConfigForm())

    def test_vendor_presets_are_not_changed(self):
        # Appliance presets mirror the vendor's requirements; they keep their own values.
        cisco = [p for group in HARDWARE_PRESETS.values() for p in group if p["key"] == "cisco-8000v"]
        self.assertEqual(len(cisco), 1)
        self.assertIn("ballooning", cisco[0]["config"])
