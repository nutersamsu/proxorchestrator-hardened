"""Phase 3: backups, restore and storage content."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import QueryDict
from django.test import Client, TestCase, override_settings

from apps.backups import logic as bl
from apps.core.models import UserProfile
from apps.proxmox.api import ProxmoxAPIError
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
UPID = "UPID:pve:00000001:00000002:6AFB7900:vzdump:100:proxorchestrator@pve!app:"
VOL = "hd3tb:backup/vzdump-qemu-100-2026_11_08-06_52_12.vma.zst"
CTVOL = "hd3tb:backup/vzdump-lxc-101-2026_11_15-02_32_37.tar.zst"
GUESTS = [{"vmid": 100, "name": "server", "type": "qemu", "status": "running"},
          {"vmid": 101, "name": "jellyfin", "type": "lxc", "status": "stopped"}]
STORAGES = [{"storage": "hd3tb", "type": "dir", "content": "images,backup,iso,vztmpl", "active": 1, "enabled": 1,
             "total": 100, "used": 50, "avail": 50},
            {"storage": "local-lvm", "type": "lvmthin", "content": "images,rootdir", "active": 1, "enabled": 1}]
JOB = {"id": "22d9f3fb-79e9", "type": "vzdump", "vmid": "100,101", "storage": "hd3tb", "schedule": "sun 02:30",
       "script": "/usr/local/sbin/hook.sh", "prune-backups": {"keep-last": "4"}, "notes-template": "{{guestname}}",
       "enabled": 1, "mode": "snapshot", "compress": "zstd", "next-run": 1795311000, "comment": "weekly"}


def _client():
    user = User.objects.create_user("u", password="pw-1234567890", is_staff=True)
    UserProfile.objects.update_or_create(user=user, defaults={"must_change_password": False})
    c = Client()
    c.force_login(user)
    return c


def _configure():
    with mock.patch("apps.core.nginx_helper._run"):
        ProxmoxConfig.objects.update_or_create(
            pk=1, defaults={"host": "192.0.2.10", "is_configured": True, "default_node": "pve",
                            "api_token_id": "t@pve!x", "api_token_secret": "s"})


class LogicTests(TestCase):
    def test_volid_validation(self):
        self.assertEqual(bl.valid_volid(VOL), "hd3tb")
        for bad in ("", "hd3tb", "hd3tb:../etc/passwd", "hd3tb:backup/../x", "a b:x", "x:/abs", "x:a//b", "x:a;b"):
            self.assertIsNone(bl.valid_volid(bad), bad)

    def test_describe_volume(self):
        guests = {100: {"name": "server", "type": "qemu"}}
        b = bl.describe_volume({"volid": VOL, "size": 32191640378, "ctime": 1794117132}, guests)
        self.assertEqual((b["vmid"], b["subtype"], b["guest_name"]), (100, "qemu", "server"))
        self.assertTrue(b["guest_exists"])
        self.assertEqual(b["size_h"], "29.98 GiB")
        orphan = bl.describe_volume({"volid": CTVOL}, guests)
        self.assertFalse(orphan["guest_exists"])  # 101 not a guest here

    def test_job_run_params_drop_script(self):
        p = bl.job_run_params(JOB)
        self.assertNotIn("script", p)
        self.assertNotIn("schedule", p)
        self.assertNotIn("id", p)
        self.assertEqual(p["prune-backups"], "keep-last=4")
        self.assertEqual(p["vmid"], "100,101")
        j = bl.describe_job(JOB)
        self.assertEqual(j["selection"], "VMs/CTs 100, 101")
        self.assertTrue(j["has_script"])

    def test_backup_form(self):
        guests = {100: {}, 101: {}}
        post = QueryDict(mutable=True)
        post.setlist("vmid", ["101", "100", "100"])
        post.update({"storage": "hd3tb", "mode": "snapshot", "compress": "zstd", "notes": "{{guestname}}", "protected": "1"})
        p = bl.parse_backup_form(post, guests, {"hd3tb"})
        self.assertEqual(p, {"vmid": "100,101", "storage": "hd3tb", "mode": "snapshot", "compress": "zstd",
                             "notes-template": "{{guestname}}", "protected": 1})
        for change in ({"storage": "local-lvm"}, {"mode": "x"}, {"compress": "xz"}, {"notes": "a\nb"}):
            bad = post.copy()
            bad.update(change)
            if "storage" in change:
                bad.setlist("storage", [change["storage"]])
            with self.assertRaises(bl.BackupError):
                bl.parse_backup_form(bad, guests, {"hd3tb"})
        bad = post.copy()
        bad.setlist("vmid", ["999"])
        with self.assertRaises(bl.BackupError):
            bl.parse_backup_form(bad, guests, {"hd3tb"})

    def test_restore_form(self):
        opts = bl.parse_restore_form({"target_vmid": "150", "unique": "1"}, "qemu", {100}, 100)
        self.assertEqual(opts, {"vmid": 150, "storage": None, "force": False, "unique": True, "start": False})
        with self.assertRaises(bl.BackupError):
            bl.parse_restore_form({"target_vmid": "100"}, "qemu", {100}, 100)  # in use, no overwrite
        with self.assertRaises(bl.BackupError):
            bl.parse_restore_form({"target_vmid": "100", "overwrite": "1", "confirm_overwrite": "10"}, "qemu", {100}, 100)
        opts = bl.parse_restore_form({"target_vmid": "100", "overwrite": "1", "confirm_overwrite": "100"}, "lxc", {100}, 100)
        self.assertTrue(opts["force"])
        self.assertFalse(opts["unprivileged"])
        for bad in ("99", "abc", "1;2", ""):
            with self.assertRaises(bl.BackupError):
                bl.parse_restore_form({"target_vmid": bad}, "qemu", set(), 100)

    def test_summarize_config(self):
        text = "name: web\nmemory: 2048\nnet0: virtio=AA,bridge=vmbr0\ndescription: x\n[snap1]\nmemory: 1"
        self.assertEqual(bl.summarize_config(text), ["name: web", "memory: 2048", "net0: virtio=AA,bridge=vmbr0"])


def _api_mocks(test):
    patches = [
        mock.patch("apps.proxmox.api.ProxmoxAPI._get", side_effect=lambda path, **kw: GUESTS if path == "/cluster/resources" else {}),
        mock.patch("apps.proxmox.api.ProxmoxAPI.get_storage", return_value=STORAGES),
        mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value={"/": {"VM.Backup": 1, "Datastore.AllocateSpace": 1}}),
    ]
    for p in patches:
        p.start()
        test.addCleanup(p.stop)


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class ViewTests(TestCase):
    def setUp(self):
        cache.clear()
        _configure()
        self.c = _client()
        _api_mocks(self)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_backup_jobs", return_value=[JOB])
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_content", return_value=[
        {"volid": VOL, "size": 10, "ctime": 1794117132, "vmid": 100, "subtype": "qemu", "notes": "<b>n</b>"},
        {"volid": CTVOL, "size": 10, "ctime": 1794706357, "vmid": 101, "subtype": "lxc", "protected": 1}])
    def test_index(self, content, _jobs):
        r = self.c.get("/backups/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "sun 02:30")
        self.assertContains(r, "server")
        self.assertContains(r, "&lt;b&gt;n&lt;/b&gt;")
        self.assertContains(r, "Run now")
        # protected backup: no delete button for it
        self.assertEqual(r.content.decode().count("openVolDelete(this)\" title"), 1)
        content.assert_called_once_with("pve", "hd3tb", content="backup", vmid=None)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.vzdump", return_value=UPID)
    def test_backup_now(self, vz):
        r = self.c.post("/backups/new/", {"vmid": ["100"], "storage": "hd3tb", "mode": "snapshot", "compress": "zstd"})
        self.assertEqual(r["Location"], f"/tasks/{UPID}/")
        vz.assert_called_once_with("pve", vmid="100", storage="hd3tb", mode="snapshot", compress="zstd")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.vzdump")
    def test_backup_now_rejects_non_backup_storage(self, vz):
        r = self.c.post("/backups/new/", {"vmid": ["100"], "storage": "local-lvm", "mode": "snapshot", "compress": "zstd"})
        self.assertEqual(r.status_code, 200)
        vz.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.vzdump", return_value=UPID)
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_backup_job", return_value=JOB)
    def test_job_run(self, _job, vz):
        r = self.c.post("/backups/job/22d9f3fb-79e9/run/")
        self.assertEqual(r["Location"], f"/tasks/{UPID}/")
        self.assertNotIn("script", vz.call_args.kwargs)
        self.assertEqual(self.c.post("/backups/job/..%2Fx/run/").status_code, 404)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.restore_vm", return_value=UPID)
    @mock.patch("apps.proxmox.api.ProxmoxAPI.extract_backup_config", return_value="name: server\nmemory: 4096\n")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_volume_attributes", return_value={"size": 1, "ctime": 1})
    def test_restore_page_and_new_id(self, _a, _c, restore):
        r = self.c.get(f"/backups/restore/?volid={VOL}")
        self.assertContains(r, "memory: 4096")
        self.assertContains(r, 'value="102"')  # 100 and 101 in use -> first free id
        r = self.c.post("/backups/restore/", {"volid": VOL, "target_vmid": "150", "storage": "local-lvm", "unique": "1"})
        self.assertEqual(r["Location"], f"/tasks/{UPID}/")
        restore.assert_called_once_with("pve", 150, VOL, "local-lvm", False, True, False)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.restore_vm")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.extract_backup_config", return_value="")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_volume_attributes", return_value={})
    def test_restore_overwrite_running_refused(self, _a, _c, restore):
        r = self.c.post("/backups/restore/", {"volid": VOL, "target_vmid": "100", "overwrite": "1", "confirm_overwrite": "100"})
        self.assertContains(r, "Stop 100 before restoring over it")
        restore.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.restore_lxc")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.extract_backup_config", return_value="")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_volume_attributes", return_value={})
    def test_restore_kind_mismatch_and_storage(self, _a, _c, restore):
        # CT backup over VM 100
        r = self.c.post("/backups/restore/", {"volid": CTVOL, "target_vmid": "100", "overwrite": "1", "confirm_overwrite": "100"})
        self.assertContains(r, "is a VM")
        # hd3tb has no rootdir content
        r = self.c.post("/backups/restore/", {"volid": CTVOL, "target_vmid": "150", "storage": "hd3tb"})
        self.assertContains(r, "container volumes")
        restore.assert_not_called()

    def test_restore_bad_volid(self):
        self.assertEqual(self.c.get("/backups/restore/?volid=hd3tb:../../etc/shadow").status_code, 404)
        self.assertEqual(self.c.get("/backups/restore/?volid=hd3tb:iso/x.iso").status_code, 404)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.delete_volume")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_volume_attributes", return_value={"protected": 0})
    def test_delete_needs_typed_name(self, _a, delete):
        self.c.post("/backups/delete/", {"volid": VOL, "confirm": "wrong"})
        delete.assert_not_called()
        self.c.post("/backups/delete/", {"volid": VOL, "confirm": "vzdump-qemu-100-2026_11_08-06_52_12.vma.zst"})
        delete.assert_called_once_with("pve", "hd3tb", VOL)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.delete_volume")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_volume_attributes", return_value={"protected": 1})
    def test_delete_protected_refused(self, _a, delete):
        self.c.post("/backups/delete/", {"volid": VOL, "confirm": "vzdump-qemu-100-2026_11_08-06_52_12.vma.zst"})
        delete.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_volume")
    def test_protect_and_notes(self, upd):
        r = self.c.post("/backups/protect/", {"volid": VOL, "protected": "1", "next": "//evil.example/"})
        self.assertEqual(r["Location"], "/backups/")  # unsafe next ignored
        upd.assert_called_with("pve", "hd3tb", VOL, protected=True)
        self.c.post("/backups/notes/", {"volid": VOL, "notes": "keep", "next": "/vm/100/#backups"})
        upd.assert_called_with("pve", "hd3tb", VOL, notes="keep")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_content", return_value=[
        {"volid": VOL, "vmid": 100, "subtype": "qemu", "size": 1, "ctime": 1},
        {"volid": CTVOL, "vmid": 101, "subtype": "lxc", "size": 1, "ctime": 1}])
    def test_guest_card_filters_kind(self, _c):
        r = self.c.get("/backups/guest/qemu/100/")
        self.assertContains(r, "vzdump-qemu-100")
        self.assertNotContains(r, "vzdump-lxc-101")
        self.assertContains(r, "{{guestname}}")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.vzdump", return_value=UPID)
    def test_guest_backup_now(self, vz):
        self.c.post("/backups/guest/lxc/101/now/", {"storage": "hd3tb", "mode": "stop", "compress": "lzo", "vmid": "999"})
        self.assertEqual(vz.call_args.kwargs["vmid"], "101")  # vmid comes from the URL only

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_content", return_value=[
        {"volid": "local-lvm:vm-555-disk-0", "vmid": 555, "size": 1, "format": "raw"},
        {"volid": "local-lvm:vm-100-disk-0", "vmid": 100, "size": 1, "format": "raw"}])
    def test_storage_pages(self, _c):
        r = self.c.get("/datastore/")
        self.assertContains(r, "hd3tb")
        self.assertContains(r, "50.0%")
        r = self.c.get("/datastore/local-lvm/?content=images")
        self.assertContains(r, "orphan?", count=1)
        self.assertNotContains(r, "openVolDelete(this)\" title")  # no Datastore.Allocate
        self.assertEqual(self.c.get("/datastore/bad name/").status_code, 404)
        self.assertEqual(self.c.get("/datastore/nope/").status_code, 404)
