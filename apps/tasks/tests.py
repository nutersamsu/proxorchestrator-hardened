"""Tasks pages, RRD charts and token-permission helper."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import Http404
from django.test import Client, TestCase, override_settings

from apps.core import charts
from apps.core.models import UserProfile
from apps.proxmox import perms
from apps.proxmox.api import ProxmoxAPIError
from apps.tasks import views as tv
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

UPID = "UPID:pve:003718BF:046060CA:6AFB7878:vncproxy:103:proxorchestrator@pve!app:"
UPID_RUNNING = "UPID:pve:00000001:00000002:6AFB7900:vzdump:100:root@pam:"

TASKS = [
    {"upid": UPID_RUNNING, "node": "pve", "type": "vzdump", "id": "100", "user": "root@pam",
     "starttime": 1794866000},
    {"upid": UPID, "node": "pve", "type": "vncproxy", "id": "103", "user": "proxorchestrator@pve",
     "tokenid": "app", "starttime": 1794865272, "endtime": 1794865433, "status": "OK"},
    {"upid": "UPID:pve:00000003:00000004:6AFB7000:qmstart:101:root@pam:", "node": "pve",
     "type": "qmstart", "id": "101", "user": "root@pam", "starttime": 1794860000,
     "endtime": 1794860005, "status": "start failed: QEMU exited with code 1"},
]


def _client(admin=True):
    user = User.objects.create_user("u", password="pw-1234567890", is_staff=admin)
    UserProfile.objects.update_or_create(
        user=user, defaults={"must_change_password": False, "mfa_enabled": False}
    )
    c = Client()
    c.force_login(user)
    return c


def _configure():
    with mock.patch("apps.core.nginx_helper._run"):
        ProxmoxConfig.objects.update_or_create(
            pk=1, defaults={"host": "192.0.2.10", "is_configured": True, "default_node": "pve",
                            "api_token_id": "t@pve!x", "api_token_secret": "s"},
        )


class UpidTests(TestCase):
    def test_valid_upid(self):
        f = tv.parse_upid(UPID)
        self.assertEqual(f["node"], "pve")
        self.assertEqual(f["type"], "vncproxy")
        self.assertEqual(f["user"], "proxorchestrator@pve!app")

    def test_rejects_traversal_and_garbage(self):
        for bad in ("", "UPID:pve:../../x", "UPID:pve:1:2:3:qmstart:100:root@pam:",
                    UPID + "/../../nodes", UPID.replace("vncproxy", "a/b"), "foo"):
            with self.assertRaises(Http404):
                tv.parse_upid(bad)

    def test_describe(self):
        running, ok, failed = (tv.describe(t) for t in TASKS)
        self.assertTrue(running["running"])
        self.assertEqual(running["label"], "Backup 100")
        self.assertEqual(running["guest_url"], "")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["user_display"], "proxorchestrator@pve!app")
        self.assertTrue(failed["failed"])
        self.assertEqual(failed["guest_url"], "/vm/101/")
        self.assertEqual(failed["duration"], "5s")


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class TaskViewTests(TestCase):
    def setUp(self):
        cache.clear()
        _configure()
        self.c = _client()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_tasks", return_value=(3, TASKS))
    def test_list(self, m):
        r = self.c.get("/tasks/?vmid=100&type=vzdump&errors=1&user=root@pam")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Backup 100")
        self.assertContains(r, "start failed")
        kwargs = m.call_args.kwargs
        self.assertEqual(kwargs["vmid"], "100")
        self.assertEqual(kwargs["typefilter"], "vzdump")
        self.assertTrue(kwargs["errors"])

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_tasks", return_value=(0, []))
    def test_list_ignores_bad_filters(self, m):
        r = self.c.get("/tasks/?vmid=1;rm&type=../x&user=a%20b")
        self.assertEqual(r.status_code, 200)
        kwargs = m.call_args.kwargs
        self.assertIsNone(kwargs["vmid"])
        self.assertIsNone(kwargs["typefilter"])
        self.assertIsNone(kwargs["userfilter"])

    def test_detail_rejects_bad_upid(self):
        self.assertEqual(self.c.get("/tasks/UPID:bad/").status_code, 404)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_task_log", return_value=(2, [{"n": 1, "t": "line one"}, {"n": 2, "t": "<b>x</b>"}]))
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_task_status_by_upid", return_value={"status": "running"})
    def test_log_running_polls_and_escapes(self, _s, _l):
        r = self.c.get(f"/tasks/{UPID_RUNNING}/log/")
        self.assertContains(r, "line one")
        self.assertContains(r, "&lt;b&gt;x&lt;/b&gt;")
        self.assertContains(r, 'hx-trigger="every 2s"')
        self.assertContains(r, "Stop")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_task_log", return_value=(1, [{"n": 1, "t": "TASK OK"}]))
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_task_status_by_upid", return_value={"status": "stopped", "exitstatus": "OK"})
    def test_log_finished_stops_polling(self, _s, _l):
        r = self.c.get(f"/tasks/{UPID}/log/")
        self.assertNotContains(r, "every 2s")

    def test_stop_requires_post(self):
        self.assertEqual(self.c.get(f"/tasks/{UPID}/stop/").status_code, 405)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.stop_task", side_effect=ProxmoxAPIError("denied", status_code=403))
    def test_stop_forbidden_message(self, m):
        r = self.c.post(f"/tasks/{UPID_RUNNING}/stop/", follow=False)
        self.assertEqual(r.status_code, 302)
        m.assert_called_once_with("pve", UPID_RUNNING)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_tasks", return_value=(3, TASKS))
    def test_recent_bar(self, _m):
        r = self.c.get("/tasks/recent/")
        self.assertContains(r, "Backup 100")

    def test_anonymous_redirected(self):
        r = Client().get("/tasks/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class RrdViewTests(TestCase):
    def setUp(self):
        cache.clear()
        _configure()
        self.c = _client(admin=False)

    def _samples(self, n=70):
        return [{"time": 1794860000 + i * 60, "cpu": 0.05, "maxmem": 4e9, "mem": 1e9 + i,
                 "netin": 100.0 * i, "netout": 50.0, "diskread": None if i == 10 else 1000.0,
                 "diskwrite": 0} for i in range(n)]

    def test_guest_charts(self):
        with mock.patch("apps.proxmox.api.ProxmoxAPI.get_rrddata", return_value=self._samples()) as m:
            r = self.c.get("/rrd/qemu/100/?timeframe=week&cf=MAX")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "<svg", count=4)
        self.assertContains(r, "Disk IO")
        self.assertEqual(m.call_args.kwargs, {"timeframe": "week", "cf": "MAX", "kind": "qemu", "vmid": 100})

    def test_bad_params_fall_back(self):
        with mock.patch("apps.proxmox.api.ProxmoxAPI.get_rrddata", return_value=[]) as m:
            r = self.c.get("/rrd/node/?timeframe=x&cf=y")
        self.assertContains(r, "No data for this period.")
        self.assertEqual(m.call_args.kwargs["timeframe"], "hour")
        self.assertEqual(m.call_args.kwargs["cf"], "AVERAGE")

    def test_unknown_kind_404(self):
        self.assertEqual(self.c.get("/rrd/storage/1/").status_code, 404)
        self.assertEqual(self.c.get("/rrd/qemu/").status_code, 404)
        self.assertEqual(self.c.get("/rrd/node/5/").status_code, 404)

    def test_api_error_shown(self):
        with mock.patch("apps.proxmox.api.ProxmoxAPI.get_rrddata", side_effect=ProxmoxAPIError("boom")):
            r = self.c.get("/rrd/lxc/101/")
        self.assertContains(r, "Could not load statistics: boom")


class ChartTests(TestCase):
    def test_downsample_and_gaps(self):
        times = list(range(0, 1440 * 60, 60))
        vals = [None if 100 <= i < 200 else float(i % 50) for i in range(1440)]
        c = charts.line_chart("x", times, [("a", vals)], "number", "day")
        self.assertEqual(c["svg"].count("<rect"), charts.MAX_POINTS)
        self.assertGreaterEqual(c["svg"].count(" M"), 1)  # path restarts after the gap
        self.assertFalse(c["empty"])

    def test_title_escaped(self):
        c = charts.line_chart("<script>", [1, 2], [("<i>", [1.0, 2.0])], "percent")
        self.assertNotIn("<script>", c["svg"])
        self.assertNotIn("<i>", c["svg"])

    def test_formatting(self):
        self.assertEqual(charts.fmt_value(2048, "bytes"), "2.0 KiB")
        self.assertEqual(charts.fmt_value(5 * 1024**2, "bytes_s"), "5.0 MiB/s")
        self.assertEqual(charts.fmt_value(55.4, "percent"), "55%")
        self.assertEqual(charts.fmt_value(None, "percent"), "—")


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class PermsTests(TestCase):
    PERMS = {"/": {"Sys.Audit": 1, "VM.Backup": 1}, "/vms/100": {"VM.Audit": 1}}

    def test_inheritance_and_override(self):
        self.assertTrue(perms.token_can("/vms/101", "VM.Backup", perms=self.PERMS))
        self.assertFalse(perms.token_can("/vms/100", "VM.Backup", perms=self.PERMS))
        self.assertTrue(perms.token_can("/vms/100", "VM.Audit", perms=self.PERMS))
        self.assertFalse(perms.token_can("/nodes/pve", "Sys.Modify", perms=self.PERMS))
        self.assertFalse(perms.token_can("../etc", "Sys.Audit", perms=self.PERMS))

    def test_cached_and_fail_closed(self):
        cache.clear()
        _configure()
        with mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value=self.PERMS) as m:
            self.assertTrue(perms.token_can("/", "Sys.Audit"))
            self.assertTrue(perms.token_can("/", "Sys.Audit"))
        self.assertEqual(m.call_count, 1)
        cache.clear()
        with mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", side_effect=ProxmoxAPIError("x")):
            self.assertFalse(perms.token_can("/", "Sys.Audit"))
