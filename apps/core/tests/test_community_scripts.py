"""Community-script execution regressions found on a real Proxmox (2026-11-10)."""

import asyncio
import subprocess
import tempfile
import time

from channels.layers import get_channel_layer
from django.test import SimpleTestCase

from apps.core.scripts import DIAGNOSTICS_OPT_OUT
from apps.lxc.tasks import _build_env_string

from ._redis import requires_redis


class DiagnosticsOptOut(SimpleTestCase):
    """The core no longer honours var_diagnostics and blocks on a whiptail
    dialog (default answer: Yes) the first time it runs on a host."""

    def _run(self, prepare=None):
        with tempfile.TemporaryDirectory() as d:
            snippet = DIAGNOSTICS_OPT_OUT.replace("/usr/local/community-scripts", d + "/cs")
            if prepare:
                subprocess.run(["bash", "-c", prepare.format(d=d)], check=True)
            subprocess.run(["bash", "-c", snippet + "true"], check=True)
            with open(f"{d}/cs/diagnostics") as f:
                return f.read()

    def test_creates_opt_out_when_missing(self):
        self.assertEqual(self._run(), "DIAGNOSTICS=no\n")

    def test_keeps_existing_choice(self):
        content = self._run('mkdir -p {d}/cs && echo "DIAGNOSTICS=yes" > {d}/cs/diagnostics')
        self.assertEqual(content, "DIAGNOSTICS=yes\n")


class DownloadFailureIsAnError(SimpleTestCase):
    """bash -c "$(curl URL)" exited 0 on a 404, so a job whose script no
    longer existed upstream was reported as successful."""

    def _run_with_fake_curl(self, curl_body):
        import os
        import shlex
        from apps.core.scripts import fetch_and_run
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "curl")
            with open(fake, "w") as f:
                f.write("#!/bin/sh\n" + curl_body + "\n")
            os.chmod(fake, 0o755)
            env = dict(os.environ, PATH=d + ":" + os.environ["PATH"])
            return subprocess.run(
                ["bash", "-c", fetch_and_run(shlex.quote("https://example.invalid/x.sh"))],
                env=env, capture_output=True, text=True)

    def test_404_fails(self):
        res = self._run_with_fake_curl("exit 22")
        self.assertEqual(res.returncode, 97)
        self.assertIn("could not download", res.stderr)

    def test_empty_download_fails(self):
        self.assertEqual(self._run_with_fake_curl("exit 0").returncode, 97)

    def test_script_runs_and_exit_code_propagates(self):
        res = self._run_with_fake_curl("echo 'echo ran; exit 5'")
        self.assertEqual(res.returncode, 5)
        self.assertIn("ran", res.stdout)


class CatalogRefreshTasksRegistered(SimpleTestCase):
    """The VM 'refresh catalog' task lived in vm_tasks.py, which Celery's
    autodiscovery never imported: the button failed with NotRegistered."""

    def test_both_refresh_tasks_are_registered(self):
        from proxorchestrator.celery import app
        app.loader.import_default_modules()
        self.assertIn("vmcreator.refresh_vm_community_catalog", app.tasks)
        self.assertIn("lxc.refresh_community_catalog", app.tasks)


class TemplateStorage(SimpleTestCase):

    def test_template_storage_passed_to_script(self):
        env = _build_env_string({"template_storage": "local", "container_storage": "local-lvm"})
        self.assertIn("var_template_storage=local", env)
        self.assertIn("var_container_storage=local-lvm", env)

    def test_template_storage_is_shell_quoted(self):
        env = _build_env_string({"template_storage": "x; rm -rf /"})
        self.assertIn("var_template_storage='x; rm -rf /'", env)


class ContainerIdDetection(SimpleTestCase):

    def test_current_and_old_output(self):
        from apps.lxc.consumers import _VMID_RE
        self.assertEqual(_VMID_RE.search("✔️  Container 103 created").group(1), "103")
        self.assertEqual(_VMID_RE.search("Creating LXC CT 205 ...").group(1), "205")
        self.assertIsNone(_VMID_RE.search("Container started"))

    def test_colourised_output_from_real_run(self):
        from apps.lxc.consumers import _ANSI_RE, _VMID_RE
        raw = "\x1b[K  ✔️  \x1b[1;92mContainer \x1b[36m104\x1b[m created\x1b[m"
        self.assertIsNone(_VMID_RE.search(raw))  # why the ANSI strip is needed
        self.assertEqual(_VMID_RE.search(_ANSI_RE.sub("", raw)).group(1), "104")


class CompletionNoticeAfterReconnect(SimpleTestCase):
    """The monitor thread belongs to the consumer that started the script;
    after a browser reconnect the DONE/exit notices went to the dead socket."""

    def test_notice_reaches_reattached_socket(self):
        from apps.lxc.consumers import CommunityScriptTerminalConsumer
        first = CommunityScriptTerminalConsumer()
        second = CommunityScriptTerminalConsumer()
        received = []

        class Bridge:
            control_callback = None

        bridge = Bridge()
        first.bridge = second.bridge = bridge
        bridge.control_callback = lambda t, **k: received.append(("first", t))
        bridge.control_callback = lambda t, **k: received.append(("second", t))  # reattach
        first._notify("exit", code=0)  # monitor thread of the first consumer
        self.assertEqual(received, [("second", "exit")])

        bridge.control_callback = None  # everyone detached
        first._notify("exit", code=0)
        self.assertEqual(len(received), 1)


@requires_redis
class ChannelLayerIdleWait(SimpleTestCase):
    """With redis-py >= 6 an idle receive() raised TimeoutError after 5 s,
    which closed every script terminal right after it opened."""

    def test_idle_receive_does_not_raise(self):
        async def wait():
            layer = get_channel_layer()
            channel = await layer.new_channel()
            started = time.time()
            try:
                await asyncio.wait_for(layer.receive(channel), timeout=8)
            except asyncio.TimeoutError:
                return time.time() - started
            return None

        waited = asyncio.run(wait())
        self.assertIsNotNone(waited)
        self.assertGreaterEqual(waited, 7.5)
