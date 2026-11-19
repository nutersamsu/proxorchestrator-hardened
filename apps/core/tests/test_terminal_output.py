"""Community-script terminal output: log cleaning, VMID detection, no reload loop."""

from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from apps.lxc.tasks import _clean_terminal_output as lxc_clean
from apps.vmcreator import consumers as vm_consumers

BASE_DIR = Path(settings.BASE_DIR)
WHIPTAIL = "\x1b[?1049h\x1b[?25l\x1b[1;1H\x1b[32mUsing Virtual Machine ID: 104\x1b[0m\x1b(B\x1b=\n"


class TerminalOutputTests(SimpleTestCase):
    def test_private_mode_escapes_are_removed(self):
        for clean in (lxc_clean, vm_consumers._clean_terminal_output):
            out = clean(WHIPTAIL * 3)
            self.assertNotIn("\x1b", out)
            self.assertNotIn("[?1049h", out)
            self.assertIn("Using Virtual Machine ID: 104", out)

    def test_new_vm_found_by_before_after_diff(self):
        api = mock.Mock()
        api.get_vms.side_effect = [[{"vmid": 100}, {"vmid": 102}], [{"vmid": 100}, {"vmid": 102}, {"vmid": 104}]]
        api.get_lxcs.return_value = [{"vmid": 101}]
        cfg = mock.Mock()
        cfg.get_api_client.return_value = api
        with mock.patch.object(vm_consumers.ProxmoxConfig, "get_config", return_value=cfg):
            before = vm_consumers._node_vmids("pve")
            after = vm_consumers._node_vmids("pve")
        self.assertEqual(after - before, {104})

    def test_vmid_listing_failure_returns_none(self):
        with mock.patch.object(vm_consumers.ProxmoxConfig, "get_config", side_effect=RuntimeError("down")):
            self.assertIsNone(vm_consumers._node_vmids("pve"))

    def test_progress_pages_do_not_reload_when_already_terminal(self):
        # Any htmx swap (recent-tasks bar every 10 s) fires afterSwap; a page
        # that loads already finished must not reload, or it loops forever.
        pages = [
            "templates/vmcreator/vm_community_scripts_progress.html",
            "templates/lxc/community_scripts_progress.html",
            "templates/lxc/progress.html",
            "templates/lxc/clone_progress.html",
        ]
        for page in pages:
            src = (BASE_DIR / page).read_text(encoding="utf-8")
            self.assertIn("if (reloaded) return;", src, page)
            self.assertIn("dataset.terminal === 'true');", src, page)
