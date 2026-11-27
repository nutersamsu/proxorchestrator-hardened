"""Nexus community-script stores (LXC Store, VM Marketplace): hero with real counts, spec tiles."""

import re
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class StoreNexusTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve"})
        u = User.objects.create_user("boss", password="pw-1234567890", is_staff=True)
        UserProfile.objects.update_or_create(user=u, defaults={"must_change_password": False})
        self.c = Client()
        self.c.force_login(u)

    def _page(self, name):
        r = self.c.get(reverse(name))
        self.assertEqual(r.status_code, 200)
        return r, r.content.decode()

    def test_lxc_hero_counts_are_real(self):
        r, html = self._page("lxc_community_scripts")
        self.assertIn('class="po-card po-store-hero"', html)
        self.assertIn(f'data-count="{r.context["total_count"]}"', html)
        self.assertIn(f'data-categories="{len(r.context["categories"])}"', html)

    def test_lxc_cards_have_spec_tiles_and_deploy_links(self):
        r, html = self._page("lxc_community_scripts")
        first = r.context["page"].object_list[0]
        self.assertIn('class="cs-spec"', html)
        self.assertIn(reverse("lxc_community_scripts_deploy", args=[first["slug"]]), html)
        self.assertEqual(html.count('class="cs-specs-grid"'), len(r.context["page"].object_list))

    def test_vm_store_hero_and_tiles(self):
        r, html = self._page("vm_community_scripts")
        self.assertIn('class="po-card po-store-hero"', html)
        self.assertIn(f'data-count="{r.context["total_count"]}"', html)
        self.assertIn('class="cs-spec"', html)
        first = r.context["page"].object_list[0]
        self.assertIn(reverse("vm_community_scripts_deploy", args=[first["slug"]]), html)

    def test_no_invented_numbers(self):
        _, html = self._page("lxc_community_scripts")
        for fake in ("SHA-256 Upstream Verified", "Total deploys", "Avg deploy time"):
            self.assertNotIn(fake, html)
        self.assertIsNone(re.search(r"1\.84M", html))
