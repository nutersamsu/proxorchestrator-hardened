"""Phase 2: VM options, cloud-init, move disk, templates, power actions, CT DNS."""

from unittest import mock
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.inventory.views import effective_status
from apps.proxmox.api import ProxmoxAPIError
from apps.vmmanager import vm_options as vo
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
UPID = "UPID:pve:00000001:00000002:6AFB7900:qmmove:100:proxorchestrator@pve!app:"
KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID/eo19qq9avA07Q4o4OE2UpjAYhYJMzSYW/X4NAlGDo me@host"

RAW = {
    "name": "web", "ostype": "l26", "agent": "1,fstrim_cloned_disks=1", "startup": "order=2,up=30",
    "hotplug": "network,disk", "tags": "prod;web", "vga": "qxl,memory=32", "scsihw": "virtio-scsi-single",
    "net0": "virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0", "net1": "virtio=AA:BB:CC:DD:EE:00,bridge=vmbr1",
    "ide2": "local-lvm:vm-100-cloudinit,media=cdrom", "ipconfig0": "ip=192.0.2.5/24,gw=192.0.2.1,ip6=auto",
    "ciuser": "debian", "cipassword": "**********", "sshkeys": "ssh-ed25519%20AAAA%20x%0A",
    "hostpci0": "0000:01:00.0,pcie=1", "usb0": "host=1234:5678", "memory": "2048",
}


def _client(admin=True):
    user = User.objects.create_user("u", password="pw-1234567890", is_staff=admin)
    UserProfile.objects.update_or_create(user=user, defaults={"must_change_password": False})
    c = Client()
    c.force_login(user)
    return c


def _configure():
    with mock.patch("apps.core.nginx_helper._run"):
        ProxmoxConfig.objects.update_or_create(
            pk=1, defaults={"host": "192.0.2.10", "is_configured": True, "default_node": "pve",
                            "api_token_id": "t@pve!x", "api_token_secret": "s"})


class OptionParsingTests(TestCase):
    def test_build_options(self):
        o = vo.build_options(RAW)
        self.assertTrue(o["opt_agent"])
        self.assertTrue(o["opt_agent_fstrim"])
        self.assertEqual(o["opt_startup_order"], "2")
        self.assertEqual(o["opt_hotplug"], ["disk", "network"])
        self.assertEqual(o["opt_tags"], ["prod", "web"])
        self.assertEqual((o["opt_vga"], o["opt_vga_memory"]), ("qxl", "32"))
        self.assertTrue(o["opt_tablet"])  # PVE default when unset

    def test_build_options_defaults(self):
        o = vo.build_options({})
        self.assertEqual(o["opt_hotplug"], ["disk", "network", "usb"])
        self.assertEqual(o["opt_vga"], "std")
        self.assertFalse(o["opt_agent"])

    def _post(self, **extra):
        data = {"ostype": "l26", "vga": "std", "scsihw": "virtio-scsi-single", "agent": "1",
                "tablet": "1", "acpi": "1", "kvm": "1", "hotplug_disk": "1", "hotplug_network": "1"}
        data.update(extra)
        return data

    def test_parse_options(self):
        kw, delete = vo.parse_options_form(self._post(startup_order="3", startup_down="60",
                                                      tags="Prod web;prod", agent_fstrim="1"))
        self.assertEqual(kw["startup"], "order=3,down=60")
        self.assertEqual(kw["tags"], "prod;web")
        self.assertEqual(kw["agent"], "enabled=1,fstrim_cloned_disks=1")
        self.assertEqual(kw["hotplug"], "disk,network")
        self.assertEqual(kw["protection"], 0)
        self.assertIn("vga", delete)

    def test_parse_options_rejects_bad_values(self):
        for bad in ({"ostype": "evil"}, {"vga": "std;rm"}, {"scsihw": "x"}, {"tags": "a,b$c"},
                    {"startup_order": "-1"}, {"startup_up": "abc"}, {"vga_memory": "9999"}):
            with self.assertRaises(vo.OptionError):
                vo.parse_options_form(self._post(**bad))

    def test_hotplug_all_off(self):
        data = self._post()
        data.pop("hotplug_disk")
        data.pop("hotplug_network")
        kw, _ = vo.parse_options_form(data)
        self.assertEqual(kw["hotplug"], "0")

    def test_other_hardware(self):
        keys = [h["key"] for h in vo.other_hardware(RAW)]
        self.assertIn("hostpci0", keys)
        self.assertIn("usb0", keys)
        self.assertNotIn("memory", keys)


class CloudInitParsingTests(TestCase):
    def test_fields(self):
        ci = vo.cloudinit_fields(RAW)
        self.assertEqual(ci["drive"], "ide2")
        self.assertTrue(ci["password_set"])
        self.assertEqual(ci["sshkeys"], "ssh-ed25519 AAAA x")
        n0, n1 = ci["interfaces"]
        self.assertEqual((n0["mode4"], n0["ip4"], n0["gw4"], n0["mode6"]), ("static", "192.0.2.5/24", "192.0.2.1", "auto"))
        self.assertEqual(n1["mode4"], "none")

    def _post(self, **extra):
        data = {"ciuser": "debian", "sshkeys": KEY, "nameserver": "1.1.1.1 9.9.9.9",
                "searchdomain": "home.arpa", "citype": "", "ciupgrade": "1",
                "mode4_0": "static", "ip4_0": "192.0.2.50/24", "gw4_0": "192.0.2.1",
                "mode6_0": "none", "mode4_1": "dhcp", "mode6_1": "auto"}
        data.update(extra)
        return data

    def test_parse(self):
        kw, delete = vo.parse_cloudinit_form(self._post(), RAW)
        self.assertEqual(kw["ipconfig0"], "ip=192.0.2.50/24,gw=192.0.2.1")
        self.assertEqual(kw["ipconfig1"], "ip=dhcp,ip6=auto")
        self.assertEqual(unquote(kw["sshkeys"]), KEY + "\n")
        self.assertNotIn(" ", kw["sshkeys"])
        self.assertNotIn("cipassword", kw)          # empty = keep
        self.assertNotIn("cipassword", delete)
        self.assertIn("citype", delete)

    def test_password_set_and_clear(self):
        kw, _ = vo.parse_cloudinit_form(self._post(cipassword="s3cret!"), RAW)
        self.assertEqual(kw["cipassword"], "s3cret!")
        _, delete = vo.parse_cloudinit_form(self._post(cipassword="x", clear_password="1"), RAW)
        self.assertIn("cipassword", delete)

    def test_rejects(self):
        for bad in ({"ciuser": "Root;x"}, {"sshkeys": "not a key"}, {"sshkeys": KEY + "\nssh-rsa bad key\x00"},
                    {"nameserver": "1.1.1.1;rm"}, {"searchdomain": "bad_domain!"},
                    {"ip4_0": "192.0.2.50"}, {"ip4_0": "2001:db8::1/64"}, {"gw4_0": "x"},
                    {"mode4_0": "weird"}, {"citype": "x"}, {"cipassword": "a\nb"}):
            with self.assertRaises(vo.OptionError, msg=str(bad)):
                vo.parse_cloudinit_form(self._post(**bad), RAW)

    def test_ct_dns(self):
        kw, delete = vo.parse_ct_dns_form({"hostname": "web-1.home.arpa", "nameserver": "", "searchdomain": "home.arpa"})
        self.assertEqual(kw, {"hostname": "web-1.home.arpa", "searchdomain": "home.arpa"})
        self.assertEqual(delete, ["nameserver"])
        for bad in ({"hostname": "bad host"}, {"hostname": "ok", "nameserver": "x.y"}):
            with self.assertRaises(vo.OptionError):
                vo.parse_ct_dns_form(bad)


class StatusTests(TestCase):
    def test_paused(self):
        self.assertEqual(effective_status({"status": "running", "qmpstatus": "paused"}), "paused")
        self.assertEqual(effective_status({"status": "running", "qmpstatus": "running"}), "running")
        self.assertEqual(effective_status({"status": "stopped"}), "stopped")


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class ViewTests(TestCase):
    def setUp(self):
        cache.clear()
        _configure()
        self.c = _client()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value={"/": {"VM.Audit": 1}})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_config", return_value={"ostype": "l26", "tablet": 1, "tags": "a"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_status", return_value={"status": "stopped"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_vm_config")
    def test_options_save_sends_only_changes(self, upd, _st, _cfg, _perm):
        r = self.c.post("/vm/100/options/", {"ostype": "win11", "vga": "virtio", "scsihw": "lsi", "tags": "a",
                                             "tablet": "1", "acpi": "1", "kvm": "1", "hotplug_disk": "1",
                                             "hotplug_network": "1", "hotplug_usb": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(upd.call_args.kwargs, {"ostype": "win11", "vga": "virtio"})

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value={"/": {"VM.Audit": 1}})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_config", return_value={"startup": "order=1"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_vm_config")
    def test_options_startup_needs_sys_modify(self, upd, _cfg, _perm):
        self.c.post("/vm/100/options/", {"ostype": "other", "vga": "std", "scsihw": "lsi", "startup_order": "2",
                                         "tablet": "1", "acpi": "1", "kvm": "1"})
        upd.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value={"/": {"VM.Audit": 1}})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_config", return_value={"startup": "order=1"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_status", return_value={"status": "stopped"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_vm_config")
    def test_options_unchanged_startup_is_not_sent(self, upd, _st, _cfg, _perm):
        self.c.post("/vm/100/options/", {"ostype": "l26", "vga": "std", "scsihw": "lsi", "startup_order": "1",
                                         "tablet": "1", "acpi": "1", "kvm": "1"})
        self.assertNotIn("startup", upd.call_args.kwargs)

    def test_only_changes_normalisation(self):
        cur = {"agent": "1,fstrim_cloned_disks=1", "hotplug": "disk,network", "tags": "a;b"}
        kw, dels = vo.only_changes(cur, {"agent": "enabled=1,fstrim_cloned_disks=1", "hotplug": "network,disk",
                                         "tags": "a;b", "kvm": 1, "freeze": 0}, ["vga", "tags"])
        self.assertEqual(kw, {})
        self.assertEqual(dels, ["tags"])

    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_vm_config")
    def test_options_invalid_not_sent(self, upd):
        self.c.post("/vm/100/options/", {"ostype": "nope", "vga": "std", "scsihw": "lsi"})
        upd.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.regenerate_cloudinit")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_vm_config")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_config", return_value=RAW)
    def test_cloudinit_save_and_regenerate(self, _cfg, upd, regen):
        r = self.c.post("/vm/100/cloudinit/save/", {"ciuser": "debian", "mode4_0": "dhcp", "regenerate": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(upd.call_args.kwargs["ipconfig0"], "ip=dhcp")
        regen.assert_called_once()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_cloudinit_pending", return_value=[{"key": "ciuser", "pending": "x"}])
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_config", return_value=RAW)
    def test_cloudinit_partial(self, _cfg, _p):
        r = self.c.get("/vm/100/cloudinit/")
        self.assertContains(r, "Not yet in the cloud-init image")
        self.assertContains(r, "192.0.2.5/24")
        self.assertNotContains(r, "**********")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_vm_config")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_config", return_value={"ide2": "local:iso/x.iso,media=cdrom"})
    def test_cloudinit_add_uses_free_slot(self, _cfg, upd):
        self.c.post("/vm/100/cloudinit/add/", {"storage": "local-lvm"})
        self.assertEqual(upd.call_args.kwargs, {"ide0": "local-lvm:cloudinit"})

    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_vm_config")
    def test_cloudinit_add_bad_storage(self, upd):
        self.c.post("/vm/100/cloudinit/add/", {"storage": "../x"})
        upd.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.move_vm_disk", return_value=UPID)
    def test_move_disk_redirects_to_task(self, mv):
        r = self.c.post("/vm/100/disks/move/", {"disk": "scsi0", "storage": "hd3tb", "delete_source": "1"})
        self.assertEqual(r["Location"], f"/tasks/{UPID}/")
        mv.assert_called_once_with("pve", 100, "scsi0", "hd3tb", delete=True, fmt=None)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.move_vm_disk")
    def test_move_disk_validation(self, mv):
        for data in ({"disk": "scsi0;rm", "storage": "x"}, {"disk": "unused0", "storage": "x"},
                     {"disk": "scsi0", "storage": "a/b"}, {"disk": "scsi0", "storage": "x", "format": "exe"}):
            self.c.post("/vm/100/disks/move/", data)
        mv.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.convert_vm_to_template")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_status", return_value={"status": "running"})
    def test_template_requires_stopped(self, _st, conv):
        self.c.post("/vm/100/template/", {"confirm_vmid": "100"})
        conv.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.convert_vm_to_template", return_value=UPID)
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_status", return_value={"status": "stopped"})
    def test_template_requires_confirmation(self, _st, conv):
        self.c.post("/vm/100/template/", {"confirm_vmid": "101"})
        conv.assert_not_called()
        r = self.c.post("/vm/100/template/", {"confirm_vmid": "100"})
        conv.assert_called_once()
        self.assertEqual(r["Location"], f"/tasks/{UPID}/")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.suspend_vm")
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_status", return_value={"status": "running", "name": "web"})
    def test_hibernate_action(self, _st, susp):
        r = self.c.post("/inventory/100/action/hibernate/")
        self.assertEqual(r.status_code, 200)
        susp.assert_called_once_with("pve", 100, todisk=True)

    @mock.patch("apps.proxmox.api.ProxmoxAPI.agent_get", side_effect=ProxmoxAPIError("not running", status_code=500))
    def test_agent_not_running(self, _a):
        r = self.c.get("/vm/100/agent/")
        self.assertContains(r, "Guest agent not running")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_vm_agent_interfaces", return_value=[
        {"name": "lo"}, {"name": "eth0", "hardware-address": "aa", "ip-addresses": [
            {"ip-address": "192.0.2.9", "prefix": 24}, {"ip-address": "fe80::1", "prefix": 64}]}])
    @mock.patch("apps.proxmox.api.ProxmoxAPI.agent_get", side_effect=lambda n, v, cmd: {
        "get-osinfo": {"pretty-name": "Debian GNU/Linux 13", "kernel-release": "6.12"},
        "get-host-name": {"host-name": "web"},
        "get-fsinfo": [{"mountpoint": "/", "type": "ext4", "total-bytes": 100, "used-bytes": 50}]}[cmd])
    def test_agent_info(self, _a, _i):
        r = self.c.get("/vm/100/agent/")
        self.assertContains(r, "Debian GNU/Linux 13")
        self.assertContains(r, "192.0.2.9/24")
        self.assertNotContains(r, "fe80")
        self.assertContains(r, "50.0%")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.move_lxc_volume", return_value=UPID)
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_lxc_status", return_value={"status": "running"})
    def test_lxc_move_rootfs_needs_stop(self, _st, mv):
        self.c.post("/lxc/101/volume/move/", {"volume": "rootfs", "storage": "hd3tb"})
        mv.assert_not_called()
        r = self.c.post("/lxc/101/volume/move/", {"volume": "mp0", "storage": "hd3tb"})
        mv.assert_called_once_with("pve", 101, "mp0", "hd3tb", delete=False)
        self.assertEqual(r["Location"], f"/tasks/{UPID}/")

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_lxc_config", return_value={"hostname": "old", "searchdomain": "x.test"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_lxc_status", return_value={"status": "running"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_lxc_config")
    def test_lxc_dns_section(self, upd, _st, _cfg):
        self.c.post("/lxc/101/settings/", {"section": "dns", "hostname": "ct1", "nameserver": "192.0.2.53"})
        self.assertEqual(upd.call_args.kwargs, {"hostname": "ct1", "nameserver": "192.0.2.53", "delete": "searchdomain"})
        upd.reset_mock()
        self.c.post("/lxc/101/settings/", {"section": "dns", "hostname": "bad host"})
        upd.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value={"/": {"VM.Audit": 1}})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_lxc_config", return_value={
        "hookscript": "local:snippets/h.pl", "startup": "order=1", "onboot": 1, "features": "nesting=1"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.get_lxc_status", return_value={"status": "stopped"})
    @mock.patch("apps.proxmox.api.ProxmoxAPI.update_lxc_config")
    def test_lxc_options_unchanged_privileged_keys_not_sent(self, upd, _st, _cfg, _perm):
        base = {"section": "options", "onboot": "1", "startup": "order=1", "hookscript": "local:snippets/h.pl",
                "feature_nesting": "1", "cmode": "shell", "tty": "2"}
        self.c.post("/lxc/101/settings/", base)
        self.assertEqual(upd.call_args.kwargs, {"cmode": "shell"})
        upd.reset_mock()
        self.c.post("/lxc/101/settings/", {**base, "hookscript": ""})   # would delete it: root@pam only
        upd.assert_not_called()
        self.c.post("/lxc/101/settings/", {**base, "startup": "order=2"})  # needs Sys.Modify
        upd.assert_not_called()
