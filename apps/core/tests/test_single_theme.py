"""Nexus redesign: a single theme — no selectable themes, no light mode, nothing saved per user."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings

from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class SingleThemeTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        self.user = User.objects.create_user("u", password="pw-1234567890")
        UserProfile.objects.update_or_create(user=self.user, defaults={"must_change_password": False})
        self.c = Client()
        self.c.force_login(self.user)

    def _render_base(self):
        req = RequestFactory().get("/")
        req.user = User.objects.get(pk=self.user.pk)
        return render_to_string("base.html", {}, request=req)

    def test_theme_endpoint_gone(self):
        self.assertEqual(self.c.post("/account/theme/", {"theme": "ops"}).status_code, 404)

    def test_base_has_no_theme_machinery(self):
        html = self._render_base()
        for needle in ("theme-selector", "data-skin", "data-theme", "proxorchestrator_theme", "toggleTheme"):
            self.assertNotIn(needle, html, needle)

    def test_profile_has_no_ui_theme(self):
        self.assertNotIn("ui_theme", [f.name for f in UserProfile._meta.get_fields()])

    def test_old_local_storage_is_harmless(self):
        # nothing in the page reads or applies a theme left in localStorage by the old versions
        html = self._render_base()
        for needle in ("applyTheme", "setTheme", "prefers-color-scheme"):
            self.assertNotIn(needle, html, needle)
