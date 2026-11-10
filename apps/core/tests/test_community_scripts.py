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
