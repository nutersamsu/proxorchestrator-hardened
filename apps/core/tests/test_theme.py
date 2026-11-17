"""Phase 6: selectable themes saved per user."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings

from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class ThemeTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        self.user = User.objects.create_user("u", password="pw-1234567890")
        UserProfile.objects.update_or_create(user=self.user, defaults={"must_change_password": False})
        self.c = Client()
        self.c.force_login(self.user)

    def _profile(self):
        return UserProfile.objects.get(user=self.user)

    def test_save_valid_theme(self):
        r = self.c.post("/account/theme/", {"theme": "ops-dark"})
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self._profile().ui_theme, "ops-dark")

    def test_rejects_unknown_theme(self):
        for bad in ("", "evil", "ops-dark<script>", "OPS"):
            self.assertEqual(self.c.post("/account/theme/", {"theme": bad}).status_code, 400)
        self.assertEqual(self._profile().ui_theme, "")

    def test_requires_post_and_login(self):
        self.assertEqual(self.c.get("/account/theme/").status_code, 405)
        r = Client().post("/account/theme/", {"theme": "ops"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_csrf_enforced(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.user)
        self.assertEqual(c.post("/account/theme/", {"theme": "ops"}).status_code, 403)

    def test_first_paint_uses_profile_theme(self):
        p = self._profile()
        p.ui_theme = "ops-light"
        p.save()
        req = RequestFactory().get("/")
        req.user = User.objects.get(pk=self.user.pk)
        html = render_to_string("base.html", {}, request=req)
        self.assertIn('var serverTheme = "ops\\u002Dlight"', html)  # escapejs; JS reads "ops-light"
        self.assertIn('id="theme-selector-side"', html)
        self.assertIn("Ops — dark", html)
        self.assertIn('name="csrf-token"', html)
        self.assertIn('class="nav-toggle-btn"', html)

    def test_nexus_theme(self):
        self.assertEqual(self.c.post("/account/theme/", {"theme": "nexus"}).status_code, 204)
        self.assertEqual(self._profile().ui_theme, "nexus")
        req = RequestFactory().get("/")
        req.user = User.objects.get(pk=self.user.pk)
        html = render_to_string("base.html", {}, request=req)
        self.assertIn('var serverTheme = "nexus"', html)
        self.assertIn("NEXUS — Dark Premium", html)
        self.assertIn("'nexus'", html)          # accepted by the theme script
        self.assertIn("skin: 'nexus', mode: 'dark'", html)

    def test_nexus_css_present(self):
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static" / "css" / "proxorchestrator.css").read_text()
        self.assertIn("[data-skin='nexus']", css)
        self.assertIn("--nx-border-control: #567391", css)
        self.assertIn("@supports not ((backdrop-filter", css)

    def test_no_theme_chosen_yet(self):
        req = RequestFactory().get("/")
        req.user = User.objects.get(pk=self.user.pk)
        self.assertIn('var serverTheme = ""', render_to_string("base.html", {}, request=req))
