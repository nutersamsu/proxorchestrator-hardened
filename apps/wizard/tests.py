"""Tests for the automatic connection used by lxc-install.sh and the wizard shortcuts."""

import io
import json
import os
import tempfile
from unittest import mock

import paramiko
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.wizard.models import DiscoveredEnvironment, ProxmoxConfig

HOST_KEY = paramiko.ECDSAKey.generate()
HOST_KEY_LINE = f"{HOST_KEY.get_name()} {HOST_KEY.get_base64()} root@pve"
FP = "ab" * 32


class FakeAPI:
    def get_nodes(self):
        return [{"node": "pve"}]

    def get_storage(self, node):
        return [{"storage": "local-lvm", "avail": 10 * 1024 ** 3, "content": "images"}]

    def get_networks(self, node):
        return [{"iface": "vmbr0", "type": "bridge"}]

    def get_vms(self, node):
        return [{"vmid": 100}]


class FakeSSH:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run_checked(self, args):
        return "proxorchestrator-ok", "", 0

    def run(self, args):
        return "model name\t: Test CPU", "", 0


class ConnectProxmoxCommandTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.known_hosts = os.path.join(self.tmp.name, "known_hosts")
        ov = override_settings(SSH_KNOWN_HOSTS=self.known_hosts)
        ov.enable()
        self.addCleanup(ov.disable)
        self.keyfile = os.path.join(self.tmp.name, "pve_host_keys")
        with open(self.keyfile, "w") as fh:
            fh.write(HOST_KEY_LINE + "\n")

    def _run(self, secret="s3cr3t-uuid", **kw):
        args = {"host": "192.0.2.10", "token_id": "proxorchestrator@pve!ct120",
                "api_fingerprint": FP, "known_hosts": self.keyfile}
        args.update(kw)
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(secret + "\n")), \
             mock.patch.object(ProxmoxConfig, "get_api_client", return_value=FakeAPI()), \
             mock.patch.object(ProxmoxConfig, "get_ssh_client", return_value=FakeSSH()):
            call_command("connect_proxmox", stdout=out,
                         **{k.replace("-", "_"): v for k, v in args.items()})
        return out.getvalue()

    def test_connects_pins_and_lands_on_defaults_step(self):
        out = self._run()
        self.assertIn("Connected", out)
        cfg = ProxmoxConfig.objects.get()
        self.assertEqual(cfg.host, "192.0.2.10")
        self.assertEqual(cfg.api_token_id, "proxorchestrator@pve!ct120")
        self.assertEqual(cfg.api_token_secret, "s3cr3t-uuid")
        self.assertEqual(cfg.wizard_step, 5)
        self.assertFalse(cfg.is_configured)  # the user still confirms the defaults
        self.assertTrue(DiscoveredEnvironment.objects.filter(config=cfg).exists())
        # secret never printed
        self.assertNotIn("s3cr3t-uuid", out)
        # SSH host key pinned for the host (no trust-on-first-use)
        keys = paramiko.HostKeys(self.known_hosts)
        self.assertEqual(keys.lookup("192.0.2.10")[HOST_KEY.get_name()], HOST_KEY)
        self.assertEqual(os.stat(self.known_hosts).st_mode & 0o777, 0o600)
        # API certificate pinned
        with open(os.path.join(self.tmp.name, "proxmox_api_fingerprints.json")) as fh:
            self.assertEqual(json.load(fh), {"192.0.2.10:8006": FP})

    def test_replaces_old_pins_for_same_host(self):
        other = paramiko.ECDSAKey.generate()
        keys = paramiko.HostKeys()
        keys.add("192.0.2.10", other.get_name(), other)
        keys.save(self.known_hosts)
        self._run()
        pinned = paramiko.HostKeys(self.known_hosts).lookup("192.0.2.10")
        self.assertEqual(pinned[HOST_KEY.get_name()], HOST_KEY)

    def test_fingerprint_with_colons_accepted(self):
        self._run(api_fingerprint=":".join(["AB"] * 32))
        with open(os.path.join(self.tmp.name, "proxmox_api_fingerprints.json")) as fh:
            self.assertEqual(json.load(fh)["192.0.2.10:8006"], FP)

    def test_rejects_bad_input(self):
        with self.assertRaises(CommandError):
            self._run(token_id="root@pam")
        with self.assertRaises(CommandError):
            self._run(host="1.2.3.4; rm -rf /")
        with self.assertRaises(CommandError):
            self._run(api_fingerprint="e3b0")
        with self.assertRaises(CommandError):
            self._run(secret="")

    def test_api_failure_does_not_save(self):
        from apps.proxmox.api import ProxmoxAPIError

        class BadAPI(FakeAPI):
            def get_nodes(self):
                raise ProxmoxAPIError("401 Unauthorized", status_code=401)

        with mock.patch("sys.stdin", io.StringIO("x\n")), \
             mock.patch.object(ProxmoxConfig, "get_api_client", return_value=BadAPI()):
            with self.assertRaises(CommandError):
                call_command("connect_proxmox", host="192.0.2.10",
                             token_id="proxorchestrator@pve!ct120", stdout=io.StringIO())
        self.assertFalse(ProxmoxConfig.objects.exists())


class WizardShortcutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="S3cure-pass-for-tests!")
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        UserProfile.objects.update_or_create(user=self.user, defaults={"must_change_password": False})
        self.client = Client()
        self.client.force_login(self.user)
        ProxmoxConfig.objects.create(host="192.0.2.10", wizard_step=2)

    def test_unconfigured_app_resumes_at_saved_step(self):
        # lxc-install.sh leaves the wizard on step 5; the dashboard must not restart at step 1
        ProxmoxConfig.objects.update(wizard_step=5)
        r = self.client.get("/")
        self.assertRedirects(r, "/wizard/", fetch_redirect_response=False)
        r = self.client.get("/wizard/")
        self.assertRedirects(r, "/wizard/step/5/", fetch_redirect_response=False)

    def test_step3_suggests_least_privilege_token(self):
        ProxmoxConfig.objects.update(wizard_step=3)
        html = self.client.get("/wizard/step/3/").content.decode()
        self.assertIn("pveum user token add proxorchestrator@pve app --privsep 0", html)
        self.assertIn("proxorchestrator@pve!app", html)
        self.assertNotIn("root@pam!proxorchestrator", html)

    def test_step2_shows_manual_key_command(self):
        with mock.patch("apps.wizard.views._read_public_key",
                        return_value=("ssh-rsa AAAAtest proxorchestrator@ct", "/x/id_rsa.pub")):
            html = self.client.get("/wizard/step/2/").content.decode()
        self.assertIn("echo 'ssh-rsa AAAAtest proxorchestrator@ct' &gt;&gt; /root/.ssh/authorized_keys", html)

    def test_step2_verify_mode_advances_when_key_works(self):
        with mock.patch("apps.wizard.views._read_public_key",
                        return_value=("ssh-rsa AAAAtest c", "/x/id_rsa.pub")), \
             mock.patch("apps.wizard.views.ProxmoxSSH", return_value=FakeSSH()):
            r = self.client.post("/wizard/step/2/", {"mode": "verify"})
        self.assertRedirects(r, "/wizard/step/3/", fetch_redirect_response=False)
        self.assertEqual(ProxmoxConfig.objects.get().wizard_step, 3)

    def test_step2_verify_mode_reports_failure(self):
        class Broken(FakeSSH):
            def __enter__(self):
                raise paramiko.AuthenticationException("denied")

        with mock.patch("apps.wizard.views._read_public_key",
                        return_value=("ssh-rsa AAAAtest c", "/x/id_rsa.pub")), \
             mock.patch("apps.wizard.views.ProxmoxSSH", return_value=Broken()):
            r = self.client.post("/wizard/step/2/", {"mode": "verify"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("The key does not work yet", r.content.decode())
        self.assertEqual(ProxmoxConfig.objects.get().wizard_step, 2)
