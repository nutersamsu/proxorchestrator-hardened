"""Path traversal on the Proxmox side of the importer storage page."""

from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.importer.storage_views import proxmox_temp_path
from apps.wizard.models import ProxmoxConfig

CFG = SimpleNamespace(proxmox_temp_dir="/var/tmp/proxorchestrator/")


class ProxmoxTempPath(TestCase):

    def test_accepts_files_inside(self):
        self.assertEqual(proxmox_temp_path(CFG, "/var/tmp/proxorchestrator/abc/disk.qcow2"),
                         "/var/tmp/proxorchestrator/abc/disk.qcow2")
        self.assertEqual(proxmox_temp_path(CFG, "/var/tmp/proxorchestrator//abc/./d.vmdk"),
                         "/var/tmp/proxorchestrator/abc/d.vmdk")

    def test_rejects_traversal_and_outside(self):
        for bad in (
            "/var/tmp/proxorchestrator/../../../etc/pve/storage.cfg",
            "/var/tmp/proxorchestrator/x/../../../../var/lib/vz/images/100/vm-100-disk-0.qcow2",
            "/var/tmp/proxorchestrator",
            "/var/tmp/proxorchestrator-evil/disk.qcow2",
            "/etc/shadow",
            "relative/disk.qcow2",
            "/var/tmp/proxorchestrator/a\x00.qcow2",
            "",
        ):
            with self.subTest(path=bad):
                self.assertIsNone(proxmox_temp_path(CFG, bad))

    def test_root_temp_dir_is_refused(self):
        self.assertIsNone(proxmox_temp_path(SimpleNamespace(proxmox_temp_dir="/"), "/etc/shadow"))


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
                   SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class ProxmoxDeleteEndpoint(TestCase):

    def setUp(self):
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "10.0.0.1", "is_configured": True, "default_node": "pve",
                "proxmox_temp_dir": "/var/tmp/proxorchestrator/"})
        u = User.objects.create_user("op", password="Op-pass-123456!")
        UserProfile.objects.update_or_create(user=u, defaults={"must_change_password": False})
        self.c = Client()
        self.c.login(username="op", password="Op-pass-123456!")

    def test_traversal_never_reaches_ssh(self):
        with mock.patch.object(ProxmoxConfig, "get_ssh_client") as ssh:
            r = self.c.post("/importer/storage/delete-proxmox/",
                            {"path": "/var/tmp/proxorchestrator/../../../etc/pve/user.cfg"})
            self.assertEqual(r.status_code, 400)
            ssh.assert_not_called()

    def test_import_of_other_vm_disk_refused(self):
        r = self.c.post("/importer/storage/create-from-proxmox/",
                        {"path": "/var/tmp/proxorchestrator/../../lib/vz/images/100/vm-100-disk-0.qcow2"})
        self.assertEqual(r.status_code, 400)
