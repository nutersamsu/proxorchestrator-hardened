"""Nexus redesign strings are translated to Brazilian Portuguese."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.utils import translation

from apps.core import navigation
from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SECTIONS_EN = ["Datacenter & Cluster", "Storage & Backups", "Cyber Defense", "Tools & Automation", "System & IAM"]


@override_settings(CACHES=LOCMEM)
class NexusTranslationTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        self.u = User.objects.create_user("boss", password="pw-1234567890", is_staff=True)
        UserProfile.objects.update_or_create(user=self.u, defaults={"must_change_password": False})

    def test_menu_sections_translated(self):
        with translation.override("pt-br"):
            labels = [str(s["label"]) for s in navigation.NAV]
        self.assertEqual(labels, ["Datacenter e cluster", "Armazenamento e backups", "Defesa",
                                  "Ferramentas e automação", "Sistema e acessos"])

    def test_every_menu_item_translated(self):
        with translation.override("pt-br"):
            pt = [str(i["label"]) for s in navigation.NAV for i in s["items"]]
        en = [str(i["label"]) for s in navigation.NAV for i in s["items"]]
        same = [e for e, p in zip(en, pt) if e == p and e not in ("Dashboard", "Proxmox", "Email")]
        self.assertEqual(same, [])

    def test_shell_in_portuguese(self):
        req = RequestFactory().get("/")
        req.user = self.u
        with translation.override("pt-br"):
            html = render_to_string("base.html", {}, request=req)
        self.assertIn("Proxmox® é uma marca registrada da Proxmox Server Solutions GmbH", html)
        self.assertIn("Nova VM", html)
        for en in SECTIONS_EN:
            self.assertNotIn(en.replace("&", "&amp;"), html)
