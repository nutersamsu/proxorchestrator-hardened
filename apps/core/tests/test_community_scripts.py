"""Community-script execution regressions found on a real Proxmox (2026-11-10)."""

import asyncio
import subprocess
import tempfile
import time

from channels.layers import get_channel_layer
from django.test import SimpleTestCase

from apps.core.scripts import DIAGNOSTICS_OPT_OUT
from apps.lxc.tasks import _build_env_string


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
