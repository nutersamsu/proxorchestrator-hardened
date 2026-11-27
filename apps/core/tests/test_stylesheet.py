"""Nexus redesign: the single stylesheet (tokens from the Stitch design system, local fonts)."""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STATIC = Path(settings.BASE_DIR) / "static"
CSS = (STATIC / "css" / "proxorchestrator.css").read_text(encoding="utf-8")


class StylesheetTests(SimpleTestCase):
    def test_no_theme_selectors(self):
        self.assertNotIn("[data-theme", CSS)
        self.assertNotIn("[data-skin", CSS)

    def test_tokens_present(self):
        low = CSS.lower()
        for token in ("#0b0f19", "#06b6d4", "#3b82f6", "#10b981", "#ef4444", "blur(12px)"):
            self.assertIn(token, low, token)

    def test_fonts_exist(self):
        faces = re.findall(r"@font-face\s*{([^}]*)}", CSS)
        families = {re.search(r"font-family:\s*['\"]([^'\"]+)", f).group(1) for f in faces}
        self.assertEqual(families, {"Inter", "JetBrains Mono"})
        for face in faces:
            for url in re.findall(r"url\(['\"]?([^'\")]+)", face):
                self.assertTrue(url.startswith("/static/"), url)
                self.assertTrue((STATIC / url[len("/static/"):]).is_file(), url)
        self.assertFalse((STATIC / "fonts" / "fira").exists())

    def test_no_external_urls(self):
        self.assertNotRegex(CSS, r"https?://")

    def test_tag_variants_beat_bulma(self):
        # Bulma 0.9 styles variants as ".tag:not(body).is-light" (0,3,0): ours must match it
        self.assertIn(".tag:not(body).is-light", CSS)
        self.assertIn(".status-badge.task-badge-running::before { display: none; }", CSS)

    def test_reduced_motion_block(self):
        self.assertIn("prefers-reduced-motion: reduce", CSS)
