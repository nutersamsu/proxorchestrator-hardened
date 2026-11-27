"""Nexus dashboard: guests table, SMART card (staff only), real data, graceful failures."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.proxmox.api import ProxmoxAPIError
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
GiB = 1024 ** 3


class FakeAPI:
    def __init__(self, fail=False, disks=None):
        self.fail, self._disks = fail, disks or []

    def get_nodes(self):
        if self.fail:
            raise ProxmoxAPIError("boom")
        return [{"node": "pve", "status": "online"}]

    def get_vms(self, node):
        return [{"vmid": 105, "name": "web", "status": "stopped", "cpu": 0, "mem": 0, "maxmem": 2 * GiB},
                {"vmid": 100, "name": "server", "status": "running", "cpu": 0.25, "mem": 4 * GiB, "maxmem": 8 * GiB}]

    def get_lxcs(self, node):
        return [{"vmid": 101, "name": "jellyfin", "status": "running", "cpu": 0.1, "mem": GiB, "maxmem": 2 * GiB}]

    def _get(self, path, params=None, timeout=None):
        if path.endswith("/disks/list"):
            return self._disks
        return []


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class DashboardNexusTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        self.staff = User.objects.create_user("boss", password="pw-1234567890", is_staff=True)
        self.user = User.objects.create_user("maria", password="pw-1234567890")
        for u in (self.staff, self.user):
            UserProfile.objects.update_or_create(user=u, defaults={"must_change_password": False})

    def _get(self, user, path="/", api=None):
        c = Client()
        c.force_login(user)
        with mock.patch("apps.wizard.models.ProxmoxConfig.get_api_client", return_value=api or FakeAPI()):
            return c.get(path)

    def test_guests_merged_and_sorted(self):
        r = self._get(self.user)
        guests = r.context["guests"]
        self.assertEqual([g["vmid"] for g in guests], [100, 101, 105])
        self.assertEqual([g["kind"] for g in guests], ["vm", "ct", "vm"])
        self.assertEqual(guests[0]["cpu_pct"], 25.0)
        self.assertEqual(guests[1]["url"], "/lxc/101/detail/")

    def test_filter_counts_rendered(self):
        html = self._get(self.user).content.decode()
        self.assertIn('data-filter="running"', html)
        self.assertIn('data-filter="ct"', html)
        self.assertRegex(html, r'(?s)data-filter="running"[^>]*>.{0,200}?<b>2</b>')

    def test_non_staff_no_smart_card(self):
        html = self._get(self.user).content.decode()
        self.assertNotIn("/dashboard/disks/", html)
        self.assertEqual(self._get(self.user, "/dashboard/disks/").status_code, 403)

    def test_staff_sees_smart_card(self):
        self.assertIn("/dashboard/disks/", self._get(self.staff).content.decode())

    def test_disks_health_badges(self):
        disks = [{"devpath": "/dev/sda", "model": "Disk A", "size": 10 ** 12, "health": "PASSED", "wearout": 98},
                 {"devpath": "/dev/sdb", "model": "Disk B", "size": 10 ** 12, "health": "FAILED", "wearout": "N/A"}]
        html = self._get(self.staff, "/dashboard/disks/", FakeAPI(disks=disks)).content.decode()
        self.assertEqual(html.count("po-badge is-ok"), 1)
        self.assertEqual(html.count("po-badge is-bad"), 1)
        self.assertIn("Disk A", html)

    def test_disks_api_error_still_200(self):
        api = FakeAPI()
        api._get = mock.Mock(side_effect=ProxmoxAPIError("403 Forbidden"))
        r = self._get(self.staff, "/dashboard/disks/", api)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "unavailable")

    def test_api_down_still_200(self):
        r = self._get(self.user, api=FakeAPI(fail=True))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["guests"], [])
        self.assertContains(r, "unavailable")

    def test_not_configured_goes_to_wizard(self):
        ProxmoxConfig.objects.filter(pk=1).update(is_configured=False)
        c = Client()
        c.force_login(self.staff)
        r = c.get("/")
        self.assertEqual(r.status_code, 302)  # WizardRedirectMiddleware
        self.assertTrue(r["Location"].startswith("/wizard/"))
