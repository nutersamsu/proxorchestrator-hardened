"""Brazilian Portuguese translation and the language selector."""

from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.utils import translation

BASE_DIR = Path(settings.BASE_DIR)
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class LanguageSelectorTests(TestCase):
    def test_catalog_is_compiled_and_loaded(self):
        mo = BASE_DIR / "locale" / "pt_BR" / "LC_MESSAGES" / "django.mo"
        self.assertTrue(mo.is_file(), "run compilemessages / msgfmt for pt_BR")
        with translation.override("pt-br"):
            self.assertEqual(translation.gettext("Virtual Machines"), "Máquinas virtuais")
            # placeholders must survive translation
            msg = translation.gettext("Delete snapshot '%(name)s'? This cannot be undone.") % {"name": "s1"}
            self.assertIn("s1", msg)

    def test_login_page_follows_browser_language(self):
        resp = Client().get("/login/", HTTP_ACCEPT_LANGUAGE="pt-BR,pt;q=0.9")
        self.assertContains(resp, '<html lang="pt-br">')
        self.assertContains(resp, "Entre na sua conta")
        resp = Client().get("/login/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
        self.assertContains(resp, '<html lang="en">')
        self.assertContains(resp, "Sign in to your account")

    def test_selector_is_shown_and_public(self):
        client = Client(enforce_csrf_checks=True)
        resp = client.get("/login/")
        self.assertContains(resp, 'action="/i18n/setlang/"')
        self.assertContains(resp, "Português (Brasil)")
        token = resp.cookies["csrftoken"].value
        resp = client.post("/i18n/setlang/", {"language": "pt-br", "next": "/login/"},
                           HTTP_X_CSRFTOKEN=token)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/login/")
        self.assertEqual(resp.cookies[settings.LANGUAGE_COOKIE_NAME].value, "pt-br")
        resp = client.get("/login/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(resp, "Entre na sua conta")

    def test_selector_rejects_external_redirect(self):
        client = Client()
        resp = client.post("/i18n/setlang/", {"language": "en", "next": "https://evil.example/"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(resp.url.startswith("https://evil.example"))

    def test_help_is_served_in_the_chosen_language(self):
        help_dir = BASE_DIR / "help"
        en = Client().get("/help/dashboard/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(en.status_code, 200)
        pt = Client().get("/help/dashboard/", HTTP_ACCEPT_LANGUAGE="pt-BR")
        self.assertEqual(pt.status_code, 200)
        if (help_dir / "pt-br" / "dashboard.md").is_file():
            self.assertNotEqual(en.content, pt.content)
        # every translated page must have an English original (same slug)
        for f in (help_dir / "pt-br").glob("*.md"):
            self.assertTrue((help_dir / f.name).is_file(), f.name)

    def test_missing_help_message_is_translated(self):
        resp = Client().get("/help/no-such-page/", HTTP_ACCEPT_LANGUAGE="pt-BR")
        self.assertContains(resp, "Ainda não há ajuda para esta página.")
