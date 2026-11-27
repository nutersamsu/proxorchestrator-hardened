"""Nexus shell: sectioned sidebar (Stitch sections, real pages only), top bar, brand."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.core import navigation
from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
TRADEMARK = ("Proxmox® is a registered trademark of Proxmox Server Solutions GmbH "
             "in the EU, the U.S., and other countries.")
STAFF_ONLY = {"node_page", "pveaccess_page", "wizard_index"}


def _all_items():
    return [item for section in navigation.NAV for item in section["items"]]


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class NavigationTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            self.config, _ = ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        self.staff = User.objects.create_user("boss", password="pw-1234567890", is_staff=True)
        self.user = User.objects.create_user("maria", password="pw-1234567890")
        for u in (self.staff, self.user):
            UserProfile.objects.update_or_create(user=u, defaults={"must_change_password": False})

    def _names(self, user, url_name="dashboard"):
        return [i["url_name"] for s in navigation.sections_for(user, url_name) for i in s["items"]]

    def test_every_item_reverses(self):
        for item in _all_items():
            reverse(item["url_name"])

    def test_staff_sees_all_items(self):
        self.assertEqual(len(self._names(self.staff)), len(_all_items()))

    def test_non_staff_hides_admin_items(self):
        names = set(self._names(self.user))
        self.assertFalse(names & STAFF_ONLY)
        self.assertIn("dashboard", names)

    def test_active_item(self):
        active = [i["label"] for s in navigation.sections_for(self.staff, "lxc_export_index")
                  for i in s["items"] if i["active"]]
        self.assertEqual(active, ["Export & Import"])

    def test_no_fake_pages(self):
        labels = {i["label"] for i in _all_items()}
        self.assertFalse(labels & {"Security Audit", "Disks & Orphans"})

    def test_sections_follow_stitch(self):
        self.assertEqual([s["label"] for s in navigation.NAV],
                         ["Datacenter & Cluster", "Storage & Backups", "Cyber Defense",
                          "Tools & Automation", "System & IAM"])

    def test_brand_and_trademark(self):
        req = RequestFactory().get("/")
        req.user = self.staff
        html = render_to_string("base.html", {}, request=req)
        self.assertIn('href="https://www.proxmox.com"', html)
        self.assertIn("/static/images/proxmox/proxmox-logo-dark.svg", html)
        self.assertIn(TRADEMARK, html)
        self.assertIn('id="topbar-stats"', html)

    def test_page_actions_wrapped_for_shortcut_hiding(self):
        # pages with their own buttons (VM detail…) hide the New VM/LXC/Import shortcuts via CSS :has()
        from pathlib import Path
        from django.conf import settings
        base = (Path(settings.BASE_DIR) / "templates" / "base.html").read_text()
        self.assertIn('<span class="page-actions">{% block page_actions %}{% endblock %}</span>', base)
        css = (Path(settings.BASE_DIR) / "static" / "css" / "proxorchestrator.css").read_text()
        self.assertIn(".topbar-actions:has(.page-actions > *) .topbar-quick", css)

    def test_topbar_stats_not_configured(self):
        ProxmoxConfig.objects.filter(pk=1).update(is_configured=False)
        c = Client()
        c.force_login(self.user)
        self.assertEqual(c.get(reverse("topbar_stats")).status_code, 204)

    def test_topbar_stats_ok(self):
        data = {"node": "pve", "error": None, "summary": {
            "cpu_pct": 12.5, "memory": {"pct": 40.0, "text": "40.00% (12.80 GiB of 32.00 GiB)", "present": True}}}
        c = Client()
        c.force_login(self.user)
        with mock.patch("apps.core.node_summary.get_node_summary", return_value=data):
            r = c.get(reverse("topbar_stats"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "12.5")
        self.assertContains(r, "40")

    def test_topbar_stats_error(self):
        data = {"node": "pve", "summary": None, "error": "Could not read the node status from the Proxmox API."}
        c = Client()
        c.force_login(self.user)
        with mock.patch("apps.core.node_summary.get_node_summary", return_value=data):
            r = c.get(reverse("topbar_stats"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "unavailable")

    def test_topbar_stats_requires_login(self):
        r = Client().get(reverse("topbar_stats"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])
