"""Dashboard node summary (PVE Summary data + temperatures)."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core import node_summary as ns
from apps.core.models import UserProfile
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

HWMON_SAMPLE = """\
hwmon0|acpitz||27800|119000
hwmon1|nvme|Composite|38850|84850
hwmon1|nvme|Sensor 1|38850|
hwmon2|coretemp|Package id 0|52000|100000
hwmon2|coretemp|Core 0|49000|100000
hwmon2|coretemp|Core 1|51000|100000
hwmon3|nvme|Composite|41850|84850
hwmon4|pch_skylake||-273000|
garbage line
"""

STATUS_SAMPLE = {
    "cpu": 0.0532,
    "wait": 0.0021,
    "loadavg": ["0.31", "0.42", "0.40"],
    "memory": {"total": 16 * 1024**3, "used": 6 * 1024**3, "free": 10 * 1024**3},
    "swap": {"total": 0, "used": 0, "free": 0},
    "rootfs": {"total": 100 * 1024**3, "used": 93 * 1024**3, "avail": 7 * 1024**3},
    "uptime": 3 * 86400 + 4 * 3600 + 5 * 60,
    "cpuinfo": {"model": "Intel(R) Core(TM) i5-6500 CPU @ 3.20GHz", "cpus": 4, "sockets": 1},
    "ksm": {"shared": 0},
    "boot-info": {"mode": "efi", "secureboot": 0},
    "current-kernel": {"sysname": "Linux", "release": "6.17.2-1-pve", "version": "#1 SMP PREEMPT_DYNAMIC"},
    "pveversion": "pve-manager/9.2.0/abcdef",
}


class TemperatureParsingTests(TestCase):
    def test_parse_skips_garbage_and_impossible_values(self):
        sensors = ns.parse_hwmon(HWMON_SAMPLE)
        self.assertEqual(len(sensors), 7)
        self.assertNotIn("pch_skylake", {s["chip"] for s in sensors})

    def test_one_reading_per_device_cpu_first(self):
        temps = ns.summarize_temps(ns.parse_hwmon(HWMON_SAMPLE))
        names = [t["name"] for t in temps]
        self.assertEqual(names[0], "CPU")
        self.assertEqual(sorted(names), ["ACPI", "CPU", "NVMe 1", "NVMe 2"])
        cpu = temps[0]
        self.assertEqual(cpu["label"], "Package id 0")
        self.assertEqual(cpu["celsius"], 52.0)
        self.assertEqual([d["label"] for d in cpu["details"]], ["Core 0", "Core 1"])
        nvme = next(t for t in temps if t["name"] == "NVMe 1")
        self.assertEqual(nvme["label"], "Composite")

    def test_levels_use_crit_when_present(self):
        self.assertEqual(ns.temp_level(50), "ok")
        self.assertEqual(ns.temp_level(72), "warm")
        self.assertEqual(ns.temp_level(90), "hot")
        # NVMe crit 84.85 -> hot from ~75
        self.assertEqual(ns.temp_level(76, 84.85), "hot")

    def test_ssh_failure_is_reported_not_raised(self):
        config = mock.Mock()
        config.get_ssh_client.side_effect = OSError("no route")
        temps, err = ns.read_temperatures(config)
        self.assertEqual(temps, [])
        self.assertEqual(err, "SSH unavailable")

    def test_ssh_runs_fixed_script_without_user_input(self):
        ssh = mock.MagicMock()
        ssh.__enter__.return_value = ssh
        ssh.run.return_value = (HWMON_SAMPLE, "", 0)
        config = mock.Mock()
        config.get_ssh_client.return_value = ssh
        temps, err = ns.read_temperatures(config)
        self.assertIsNone(err)
        ssh.run.assert_called_once_with(["sh", "-c", ns.HWMON_SCRIPT])
        self.assertEqual(len(temps), 4)


class SummaryFormattingTests(TestCase):
    def test_build_summary(self):
        s = ns.build_summary(STATUS_SAMPLE)
        self.assertEqual(s["cpu_pct"], 5.3)
        self.assertEqual(s["io_delay_pct"], 0.2)
        self.assertEqual(s["loadavg"], "0.31, 0.42, 0.40")
        self.assertEqual(s["memory"]["pct"], 37.5)
        self.assertEqual(s["memory"]["total"], "16.00 GiB")
        self.assertFalse(s["swap"]["present"])
        self.assertEqual(s["rootfs"]["pct"], 93.0)
        self.assertEqual(s["uptime"], "3d 04h 05m")
        self.assertEqual(s["boot_mode"], "EFI")
        self.assertIn("4 x Intel(R) Core(TM) i5-6500", s["cpu_desc"])
        self.assertIn("(1 Socket)", s["cpu_desc"])
        self.assertEqual(s["kernel"], "Linux 6.17.2-1-pve #1 SMP PREEMPT_DYNAMIC")

    def test_build_summary_tolerates_empty_status(self):
        s = ns.build_summary({})
        self.assertEqual(s["cpu_desc"], "-")
        self.assertEqual(s["uptime"], "-")
        self.assertFalse(s["memory"]["present"])


@override_settings(CACHES=LOCMEM)
class NodeSummaryViewTests(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user("viewer", password="S3cure-pass-for-tests!")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.must_change_password = False
        profile.save()
        self.client = Client()
        self.client.force_login(user)
        ProxmoxConfig.objects.create(
            host="10.0.0.2", api_port=8006, default_node="pve",
            api_token_id="a@pve!b", api_token_secret="s", is_configured=True,
        )

    def test_requires_login(self):
        resp = Client().get("/dashboard/node-summary/")
        self.assertEqual(resp.status_code, 302)

    @mock.patch("apps.core.node_summary.read_temperatures",
                return_value=(ns.summarize_temps(ns.parse_hwmon(HWMON_SAMPLE)), None))
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_node_status", return_value=STATUS_SAMPLE)
    def test_renders_summary_and_temps(self, _status, _temps):
        resp = self.client.get("/dashboard/node-summary/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Memory usage", html)
        self.assertIn("6.00 GiB of 16.00 GiB", html)
        self.assertIn("pve-manager/9.2.0", html)
        self.assertIn("52.0 °C", html)
        self.assertIn("ns-bar is-high", html)  # root disk at 93%
        self.assertIn("width: 37.5%", html)

    @mock.patch("apps.core.node_summary.read_temperatures", return_value=([], "SSH unavailable"))
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_node_status")
    def test_api_403_shows_permission_hint(self, status, _temps):
        from apps.proxmox.api import ProxmoxAPIError
        status.side_effect = ProxmoxAPIError("GET /nodes/pve/status returned HTTP 403", status_code=403)
        resp = self.client.get("/dashboard/node-summary/")
        html = resp.content.decode()
        self.assertIn("Sys.Audit", html)
        self.assertIn("SSH unavailable", html)

    @mock.patch("apps.core.node_summary.read_temperatures", return_value=([], "x"))
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_node_status", return_value=STATUS_SAMPLE)
    def test_result_is_cached(self, status, temps):
        self.client.get("/dashboard/node-summary/")
        self.client.get("/dashboard/node-summary/")
        self.assertEqual(status.call_count, 1)
        self.assertEqual(temps.call_count, 1)
