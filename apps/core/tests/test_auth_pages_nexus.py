"""Nexus public pages (login, password recovery) and setup wizard: brand + trademark, forms intact."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
TRADEMARK = ("Proxmox® is a registered trademark of Proxmox Server Solutions GmbH "
             "in the EU, the U.S., and other countries.")


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class AuthPagesNexusTests(TestCase):
    def setUp(self):
        cache.clear()

    def _assert_brand(self, html):
        self.assertIn('class="auth-brand"', html)
        self.assertIn('href="https://www.proxmox.com"', html)
        self.assertIn("/static/images/proxmox/proxmox-logo-dark.svg", html)
        self.assertIn(TRADEMARK, html)
        self.assertNotIn("&#9889; ProxOrchestrator", html)
        self.assertNotIn("⚡ ProxOrchestrator", html)

    def test_login_brand_and_form(self):
        html = Client().get("/login/").content.decode()
        self._assert_brand(html)
        for field in ('name="username"', 'name="password"', 'name="csrfmiddlewaretoken"'):
            self.assertIn(field, html)

    def test_password_recovery_brand(self):
        self._assert_brand(Client().get("/forgot-password/").content.decode())

    def test_wizard_brand(self):
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "", "is_configured": False, "wizard_step": 1})
        u = User.objects.create_user("boss", password="pw-1234567890", is_staff=True, is_superuser=True)
        UserProfile.objects.update_or_create(user=u, defaults={"must_change_password": False})
        c = Client()
        c.force_login(u)
        r = c.get("/wizard/step/1/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('class="brand-mark"', html)
        self.assertIn(TRADEMARK, html)
