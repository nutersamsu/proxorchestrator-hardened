"""Nexus inventory pages (VMs & Guests, LXC & Containers): rows, long names, actions untouched."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
GiB = 1024 ** 3
LONG = "um-nome-de-vm-bem-comprido-para-testar-o-corte-do-layout-60c"


def _g(vmid, name, status):
    return {"vmid": vmid, "name": name, "status": status, "cpu": 0.1, "cpus": 2, "mem": GiB,
            "maxmem": 2 * GiB, "uptime": 3600 if status == "running" else 0, "template": 0}


class FakeAPI:
    def get_vms(self, node):
        return [_g(100, "server", "running"), _g(103, "xpe", "stopped"), _g(104, LONG, "stopped")]

    def get_lxcs(self, node):
        return [_g(101, "jellyfin", "running"), _g(105, LONG, "stopped")]

    def __getattr__(self, name):
        return lambda *a, **k: []


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class InventoryNexusTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        u = User.objects.create_user("boss", password="pw-1234567890", is_staff=True)
        UserProfile.objects.update_or_create(user=u, defaults={"must_change_password": False})
        self.c = Client()
        self.c.force_login(u)

    def _html(self, path):
        with mock.patch("apps.wizard.models.ProxmoxConfig.get_api_client", return_value=FakeAPI()):
            r = self.c.get(path)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_vm_rows(self):
        html = self._html("/inventory/")
        for vmid in (100, 103, 104):
            self.assertIn(f'id="vm-row-{vmid}"', html)

    def test_vm_long_name_has_title(self):
        self.assertIn(f'title="{LONG}"', self._html("/inventory/"))

    def test_vm_actions_unchanged(self):
        html = self._html("/inventory/")
        for needle in ('hx-post="/inventory/100/action/shutdown/"', 'hx-post="/inventory/100/action/reboot/"',
                       'hx-post="/inventory/100/action/stop/"', 'hx-post="/inventory/103/action/start/"',
                       'href="/vm/100/"', 'href="/vm/100/console/"'):
            self.assertIn(needle, html)

    def test_ct_rows_and_actions(self):
        html = self._html("/lxc/")
        for needle in ('id="ct-row-101"', 'id="ct-row-105"', 'hx-post="/lxc/101/action/shutdown/"',
                       'hx-post="/lxc/105/action/start/"', 'href="/lxc/101/detail/"'):
            self.assertIn(needle, html)

    def test_ct_long_name_has_title(self):
        self.assertIn(f'title="{LONG}"', self._html("/lxc/"))
