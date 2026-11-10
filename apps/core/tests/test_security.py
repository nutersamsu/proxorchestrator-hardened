"""Regression tests for the security hardening.

Each test pins down a vulnerability found in the audit of 2026-11-10 so it
cannot silently come back.
"""

import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

import paramiko
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

BASE_DIR = Path(settings.BASE_DIR)
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def make_user(username, password="S3cure-pass-for-tests!", staff=False, mfa=False):
    user = User.objects.create_user(username=username, password=password,
                                    email=f"{username}@example.test")
    user.is_staff = staff
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.must_change_password = False
    profile.mfa_enabled = mfa
    if mfa:
        profile.mfa_secret = "JBSWY3DPEHPK3PXP"
    profile.save()
    return user


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class SecurityTestCase(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(
                pk=1, defaults={"host": "10.0.0.1", "is_configured": True,
                                "default_node": "pve"})


class AllauthLocalAccountsClosed(SecurityTestCase):
    """Anyone could create an account at /accounts/signup/ and log in at
    /accounts/login/ (bypassing MFA)."""

    def test_signup_is_blocked(self):
        c = Client()
        r = c.post("/accounts/signup/", {"username": "intruder",
                                         "password1": "Xk29!pq_long_pw",
                                         "password2": "Xk29!pq_long_pw"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/login/")
        self.assertFalse(User.objects.filter(username="intruder").exists())

    def test_allauth_login_cannot_bypass_mfa(self):
        make_user("boss", staff=True, mfa=True)
        c = Client()
        r = c.post("/accounts/login/", {"login": "boss", "password": "S3cure-pass-for-tests!"})
        self.assertEqual(r["Location"], "/login/")
        self.assertNotIn("_auth_user_id", c.session)

    def test_django_admin_login_redirects_to_app_login(self):
        r = Client().get("/admin/login/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/login/"))

    def test_adapter_closed_even_if_reached(self):
        from apps.authconfig.adapters import ClosedAccountAdapter
        self.assertFalse(ClosedAccountAdapter().is_open_for_signup(None))


class AdminOnlyAreas(SecurityTestCase):
    """Any logged-in (or self-registered) user could reconfigure Proxmox,
    browse the server filesystem and run root scripts."""

    ADMIN_PATHS = [
        "/settings/proxmox/",
        "/settings/auth/",
        "/wizard/",
        "/wizard/step/1/",
        "/wizard/local-browse/?path=/etc",
        "/lxc/new/community-scripts/",
        "/vm/new/community-scripts/",
    ]

    def test_non_admin_gets_403(self):
        make_user("operator")
        c = Client()
        c.login(username="operator", password="S3cure-pass-for-tests!")
        for path in self.ADMIN_PATHS:
            with self.subTest(path=path):
                self.assertEqual(c.get(path).status_code, 403)
        r = c.post("/wizard/local-mkdir/", {"path": "/tmp/po-should-not-exist"})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(os.path.exists("/tmp/po-should-not-exist"))
        self.assertEqual(c.post("/users/1/toggle-admin/").status_code, 403)

    def test_admin_is_allowed(self):
        make_user("admin1", staff=True)
        c = Client()
        c.login(username="admin1", password="S3cure-pass-for-tests!")
        self.assertNotEqual(c.get("/wizard/step/1/").status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        r = Client().get("/inventory/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/login/"))


class LoginHardening(SecurityTestCase):

    def test_open_redirect_is_neutralised(self):
        make_user("u1")
        for evil in ("//evil.example", "https://evil.example/", "/\\evil.example"):
            with self.subTest(next=evil):
                c = Client()
                r = c.post("/login/", {"username": "u1", "password": "S3cure-pass-for-tests!",
                                       "next": evil})
                self.assertEqual(r["Location"], "/")

    def test_mfa_next_is_neutralised(self):
        make_user("u2", mfa=True)
        c = Client()
        c.post("/login/", {"username": "u2", "password": "S3cure-pass-for-tests!",
                           "next": "//evil.example"})
        self.assertEqual(c.session.get("mfa_next"), "/")

    def test_bruteforce_lockout(self):
        make_user("victim")
        c = Client()
        for _ in range(settings.LOGIN_MAX_FAILURES_PER_USER):
            c.post("/login/", {"username": "victim", "password": "wrong"})
        r = c.post("/login/", {"username": "victim", "password": "S3cure-pass-for-tests!"})
        self.assertNotIn("_auth_user_id", c.session)
        self.assertContains(r, "Too many failed attempts")

    def test_mfa_bruteforce_survives_relogin(self):
        make_user("mfauser", mfa=True)
        locked = False
        for _ in range(4):
            c = Client()
            c.post("/login/", {"username": "mfauser", "password": "S3cure-pass-for-tests!"})
            for _ in range(2):
                r = c.post("/mfa/verify/", {"code": "000000"})
            if r.status_code == 302 and r["Location"].endswith("/login/"):
                locked = True
        self.assertTrue(locked)
        from apps.core.security import login_is_locked
        req = mock.Mock(META={"REMOTE_ADDR": "127.0.0.1"})
        self.assertTrue(login_is_locked(req, "mfauser", scope="mfa"))

    @override_settings(PUBLIC_BASE_URL="https://po.example.lan:8443")
    def test_password_reset_link_ignores_host_header(self):
        from apps.emailconfig.models import EmailConfig
        make_user("resetme")
        with mock.patch.object(EmailConfig, "get_config",
                               return_value=mock.Mock(is_enabled=True)), \
                mock.patch("apps.core.views.send_mail") as send:
            Client(HTTP_HOST="testserver").post(
                "/forgot-password/", {"email": "resetme@example.test"},
                HTTP_X_FORWARDED_HOST="evil.example")
        body = send.call_args[0][1]
        self.assertIn("https://po.example.lan:8443/reset-password/", body)
        self.assertNotIn("evil.example", body)


class ConsoleProxyAuth(SecurityTestCase):
    """nginx /vm-ws/ used to forward ANY request to the Proxmox API with the
    API token attached, without authentication."""

    URI = "/vm-ws/nodes/pve/qemu/101/vncwebsocket?port=5900&vncticket=PVEVNC%3AABC"

    def _auth(self, client, uri=None):
        return client.get("/internal/console-auth/", HTTP_X_ORIGINAL_URI=uri or self.URI)

    def test_anonymous_denied(self):
        self.assertEqual(self._auth(Client()).status_code, 401)

    def test_logged_in_without_grant_denied(self):
        make_user("op")
        c = Client()
        c.login(username="op", password="S3cure-pass-for-tests!")
        self.assertEqual(self._auth(c).status_code, 403)

    def test_grant_allows_only_that_guest(self):
        make_user("op2")
        c = Client()
        c.login(username="op2", password="S3cure-pass-for-tests!")
        session = c.session
        session["console_grants"] = {"pve/qemu/101": time.time() + 60}
        session.save()
        self.assertEqual(self._auth(c).status_code, 204)
        self.assertEqual(self._auth(c, self.URI.replace("101", "102")).status_code, 403)
        for bad in ("/vm-ws/access/users", "/vm-ws/nodes/pve/qemu/101/config",
                    "/vm-ws/nodes/pve/qemu/101/vncwebsocket?port=1&vncticket=x&x=/../../access"):
            with self.subTest(uri=bad):
                self.assertEqual(self._auth(c, bad).status_code, 403)

    def test_ticket_with_special_characters(self):
        """Proxmox 9 tickets contain characters like  " < > ' ( ) — the console
        page must emit them as valid JSON and the auth check must accept the
        browser's encodeURIComponent() form."""
        from urllib.parse import quote
        from django.template.loader import render_to_string
        ticket = """,>8J6"OWP'(x)!~*:PVEVNC:6AF2E8B5::txAs<q>/S+="""
        html = render_to_string("vmmanager/console.html", {
            "vmid": 101, "vnc": {"ticket": ticket}, "error": None,
            "console_data": {"ticket": ticket, "node": "pve", "vmid": 101, "vnc_port": "5900"}})
        import json
        import re
        m = re.search(r'<script id="console-data" type="application/json">(.*?)</script>', html, re.S)
        self.assertEqual(json.loads(m.group(1))["ticket"], ticket)

        make_user("op4")
        c = Client()
        c.login(username="op4", password="S3cure-pass-for-tests!")
        session = c.session
        session["console_grants"] = {"pve/qemu/101": time.time() + 60}
        session.save()
        encoded = quote(ticket, safe="-_.!~*'()")  # == encodeURIComponent
        uri = f"/vm-ws/nodes/pve/qemu/101/vncwebsocket?port=5900&vncticket={encoded}"
        self.assertEqual(self._auth(c, uri).status_code, 204)

    def test_expired_grant_denied(self):
        make_user("op3")
        c = Client()
        c.login(username="op3", password="S3cure-pass-for-tests!")
        session = c.session
        session["console_grants"] = {"pve/qemu/101": time.time() - 1}
        session.save()
        self.assertEqual(self._auth(c).status_code, 403)


class WebSocketHardening(SecurityTestCase):
    """The root-shell WebSockets accepted cross-site handshakes and any user."""

    def _connect(self, user, origin):
        from proxorchestrator.asgi import application
        from apps.lxc.models import CommunityScriptJob
        # A finished job: a successful connect only replays the stored log,
        # so nothing is ever executed by these tests.
        job = CommunityScriptJob.objects.create(
            created_by=user, app_name="x", app_slug="x", node="pve",
            script_url="https://example.invalid/x.sh", stage="DONE")
        headers = [(b"host", b"testserver")]
        if origin:
            headers.append((b"origin", origin.encode()))

        async def run():
            comm = WebsocketCommunicator(
                application, f"/ws/lxc/community-scripts/{job.pk}/terminal/", headers=headers)
            comm.scope["user"] = user
            connected, code = await comm.connect()
            await comm.disconnect()
            return connected, code
        return async_to_sync(run)()

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_cross_site_origin_rejected(self):
        admin = make_user("wsadmin", staff=True)
        connected, _ = self._connect(admin, "https://evil.example")
        self.assertFalse(connected)

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_same_origin_admin_accepted(self):
        admin = make_user("wsadmin2", staff=True)
        connected, _ = self._connect(admin, "https://testserver")
        self.assertTrue(connected)

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_non_admin_rejected(self):
        op = make_user("wsop")
        connected, _ = self._connect(op, "https://testserver")
        self.assertFalse(connected)

    def test_trusted_script_urls(self):
        from apps.core.scripts import script_url_is_trusted
        base = "https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main"
        self.assertTrue(script_url_is_trusted(f"{base}/ct/docker.sh"))
        self.assertTrue(script_url_is_trusted(f"{base}/vm/haos-vm.sh"))
        for bad in (f"{base}/ct/../../evil.sh", "https://evil.example/ct/docker.sh",
                    f"{base}/ct/docker.sh;id", f"{base.replace('main', 'evil')}/ct/x.sh"):
            with self.subTest(url=bad):
                self.assertFalse(script_url_is_trusted(bad))


class EntraHardening(SecurityTestCase):

    def test_multi_tenant_values_rejected(self):
        from apps.authconfig.adapters import tenant_is_valid
        for bad in ("", "common", "organizations", "consumers", "Common", "a b", "x"):
            with self.subTest(tenant=bad):
                self.assertFalse(tenant_is_valid(bad))
        self.assertTrue(tenant_is_valid("72f988bf-86f1-41af-91ab-2d7cd011db47"))
        self.assertTrue(tenant_is_valid("contoso.onmicrosoft.com"))

    def test_no_takeover_of_local_account_by_email(self):
        from allauth.core.exceptions import ImmediateHttpResponse
        from apps.authconfig.adapters import AutoSignupSocialAdapter
        from apps.authconfig.models import EntraIDConfig
        EntraIDConfig.objects.update_or_create(pk=1, defaults={
            "tenant_id": "contoso.onmicrosoft.com", "client_id": "x", "is_enabled": True})
        make_user("localadmin", staff=True)
        sociallogin = mock.Mock(is_existing=False)
        sociallogin.account.provider = "microsoft"
        sociallogin.account.uid = "attacker"
        sociallogin.account.extra_data = {"mail": "localadmin@example.test",
                                          "userPrincipalName": "attacker@contoso.onmicrosoft.com"}
        request = Client().get("/login/").wsgi_request
        with mock.patch("apps.authconfig.adapters.messages"):
            with self.assertRaises(ImmediateHttpResponse):
                AutoSignupSocialAdapter().pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_allowed_domains_enforced(self):
        from allauth.core.exceptions import ImmediateHttpResponse
        from apps.authconfig.adapters import AutoSignupSocialAdapter
        from apps.authconfig.models import EntraIDConfig
        EntraIDConfig.objects.update_or_create(pk=1, defaults={
            "tenant_id": "contoso.onmicrosoft.com", "client_id": "x", "is_enabled": True,
            "allowed_domains": "contoso.com"})
        sociallogin = mock.Mock(is_existing=True)
        sociallogin.account.provider = "microsoft"
        sociallogin.account.extra_data = {"userPrincipalName": "guest@other.com"}
        request = Client().get("/login/").wsgi_request
        with mock.patch("apps.authconfig.adapters.messages"):
            with self.assertRaises(ImmediateHttpResponse):
                AutoSignupSocialAdapter().pre_social_login(request, sociallogin)


class HostKeyPinning(TestCase):
    """SSH used AutoAddPolicy (and SFTP no host-key check at all)."""

    def test_tofu_then_mismatch_rejected(self):
        from apps.proxmox import hostkeys
        with tempfile.TemporaryDirectory() as d, \
                override_settings(SSH_KNOWN_HOSTS=os.path.join(d, "known_hosts")):
            policy = hostkeys.TrustOnFirstUsePolicy()
            k1 = paramiko.ECDSAKey.generate()
            k2 = paramiko.ECDSAKey.generate()
            policy.missing_host_key(None, "pve.lan", k1)       # pinned
            policy.missing_host_key(None, "pve.lan", k1)       # same key ok
            with self.assertRaises(paramiko.BadHostKeyException):
                policy.missing_host_key(None, "pve.lan", k2)
            self.assertTrue(hostkeys.forget("pve.lan"))
            policy.missing_host_key(None, "pve.lan", k2)       # re-pinned


class NginxHelperValidation(TestCase):
    """The service user used to write nginx config via 'sudo tee' (path to
    root) and the Proxmox host was interpolated unvalidated into nginx."""

    def _load(self, tmp):
        spec = importlib.util.spec_from_loader(
            "po_nginx_helper", loader=None)
        mod = importlib.util.module_from_spec(spec)
        src = (BASE_DIR / "deploy" / "proxorchestrator-nginx-helper").read_text()
        exec(compile(src, "proxorchestrator-nginx-helper", "exec"), mod.__dict__)
        mod.CONF_DIR = tmp
        mod.WS_CONF = os.path.join(tmp, "proxmox_ws.conf")
        mod.ACME_CONF = os.path.join(tmp, "acme.conf")
        mod.NGINX = "/bin/true"
        return mod

    def _write_ws(self, mod, host, port="8006",
                  token="root@pam!po\n12345678-1234-1234-1234-123456789abc\n"):
        with mock.patch("sys.stdin", io.StringIO(token)), mock.patch("os.geteuid", return_value=0):
            mod.main(["write-ws", host, port])

    def test_injection_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = self._load(tmp)
            for host in ("pve;\n access_log /etc/cron.d/x;", "pve lan", "-t", "a/b"):
                with self.subTest(host=host), self.assertRaises(SystemExit):
                    self._write_ws(mod, host)
            with self.assertRaises(SystemExit):
                self._write_ws(mod, "pve.lan", token="root@pam!po\nsecret;}\n")
            with self.assertRaises(SystemExit):
                self._write_ws(mod, "pve.lan", port="99999")
            self.assertFalse(os.path.exists(mod.WS_CONF))

    def test_generated_conf_is_authenticated(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = self._load(tmp)
            self._write_ws(mod, "192.168.1.5")
            conf = Path(mod.WS_CONF).read_text()
            self.assertIn("auth_request        /_po_console_auth;", conf)
            self.assertIn("limit_except GET", conf)
            self.assertIn("location /vm-ws/ {\n    return 404;", conf)
            self.assertEqual(os.stat(mod.WS_CONF).st_mode & 0o777, 0o600)


class SettingsHardening(TestCase):

    def test_refuses_to_start_without_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
        env.update(SECRET_KEY="insecure-default-change-me", DEBUG="False",
                   DJANGO_SETTINGS_MODULE="proxorchestrator.settings.production")
        res = subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=BASE_DIR, env=env, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("SECRET_KEY must be set", res.stderr)

    def test_wildcard_host_dropped(self):
        env = dict(os.environ, ALLOWED_HOSTS="*",
                   DJANGO_SETTINGS_MODULE="proxorchestrator.settings.production")
        env.pop("ALLOW_ANY_HOST", None)
        res = subprocess.run(
            [sys.executable, "-c",
             "import django; django.setup(); from django.conf import settings; "
             "print(settings.ALLOWED_HOSTS)"],
            cwd=BASE_DIR, env=env, capture_output=True, text=True)
        self.assertNotIn("'*'", res.stdout)
