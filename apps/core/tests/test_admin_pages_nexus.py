"""Nexus: datacenter pages render in the new shell; staff-only pages stay staff-only."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PAGES = ("/firewall/", "/tasks/", "/datastore/", "/backups/", "/node/", "/pveaccess/")
STAFF_ONLY = ("/node/", "/pveaccess/")


class FakeAPI:
    def get_tasks(self, node, start=0, limit=50, **kw):
        return 0, []

    def get_permissions(self, *a, **k):
        return {"/": {"Sys.Audit": 1, "Datastore.Audit": 1, "VM.Audit": 1}}

    def _get(self, path, params=None, timeout=None):
        if path.startswith("/access/permissions"):
            return self.get_permissions()
        if path.endswith("/options"):
            return {"enable": 0}
        return []

    def __getattr__(self, name):
        return lambda *a, **k: []


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class AdminPagesNexusTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        self.staff = User.objects.create_user("boss", password="pw-1234567890", is_staff=True)
        self.user = User.objects.create_user("maria", password="pw-1234567890")
        for u in (self.staff, self.user):
            UserProfile.objects.update_or_create(user=u, defaults={"must_change_password": False})

    def _get(self, user, path):
        c = Client()
        c.force_login(user)
        with mock.patch("apps.wizard.models.ProxmoxConfig.get_api_client", return_value=FakeAPI()):
            return c.get(path)

    def test_pages_render_in_nexus_shell_for_staff(self):
        for path in PAGES:
            r = self._get(self.staff, path)
            self.assertEqual(r.status_code, 200, path)
            html = r.content.decode()
            self.assertIn('class="topbar page-header"', html, path)
            self.assertIn('aria-current="page"', html, path)  # its menu item is lit

    def test_staff_only_pages_still_closed(self):
        for path in STAFF_ONLY:
            self.assertIn(self._get(self.user, path).status_code, (302, 403), path)
