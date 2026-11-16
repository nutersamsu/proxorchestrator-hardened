"""Phase 5: node and Proxmox permissions pages (read-only, admin-only)."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.proxmox.api import ProxmoxAPIError
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

DATA = {
    "/nodes/pve/services": [{"name": "pveproxy", "desc": "PVE API Proxy", "state": "running", "unit-state": "enabled",
                             "active-state": "active"},
                            {"name": "corosync", "state": "dead", "unit-state": "enabled", "active-state": "inactive"}],
    "/nodes/pve/network": [{"iface": "nic0", "type": "eth", "active": 1},
                           {"iface": "vmbr0", "type": "bridge", "active": 1, "autostart": 1, "cidr": "192.0.2.11/24",
                            "gateway": "192.0.2.1", "bridge_ports": "nic0"}],
    "/nodes/pve/dns": {"search": "home.arpa", "dns1": "192.0.2.1"},
    "/nodes/pve/time": {"timezone": "Europe/Rome", "time": 1794870658},
    "/nodes/pve/hosts": {"data": "127.0.0.1 localhost\n<script>x</script>"},
    "/nodes/pve/disks/list": [{"devpath": "/dev/sda", "type": "ssd", "size": 2000398934016, "model": "Samsung",
                               "serial": "S1", "health": "PASSED", "wearout": 95}],
    "/nodes/pve/disks/lvm": {"children": [{"name": "pve", "size": 100, "free": 10, "lvcount": 3,
                                           "children": [{"name": "/dev/nvme0n1p3"}]}]},
    "/nodes/pve/disks/lvmthin": [{"vg": "pve", "lv": "data", "lv_size": 200, "used": 50, "metadata_size": 10,
                                  "metadata_used": 1}],
    "/nodes/pve/disks/zfs": [],
    "/nodes/pve/disks/directory": [],
    "/nodes/pve/disks/smart": {"health": "PASSED", "type": "text", "text": "Temperature: 44 Celsius"},
    "/nodes/pve/apt/repositories": {"standard-repos": [{"name": "No-Subscription", "status": 1, "handle": "no-subscription"},
                                                       {"name": "Test", "handle": "test"}],
                                    "files": [{"path": "/etc/apt/sources.list.d/pve.sources", "repositories": [
                                        {"Enabled": 1, "Types": ["deb"], "URIs": ["http://download.proxmox.com/debian/pve"],
                                         "Suites": ["trixie"], "Components": ["pve-no-subscription"]}]}],
                                    "errors": []},
    "/nodes/pve/apt/versions": [{"Package": "proxmox-ve", "Version": "9.2.0", "RunningKernel": "7.0.14-28-pve",
                                 "CurrentState": "Installed"},
                                {"Package": "vim", "Version": "9.1", "CurrentState": "Installed"}],
    "/nodes/pve/subscription": {"status": "notfound", "message": "There is no subscription key"},
    "/nodes/pve/certificates/info": [{"filename": "pve-ssl.pem", "subject": "/CN=pve.home.arpa", "issuer": "/CN=CA",
                                      "notbefore": 1794751882, "notafter": 1857823882, "san": ["pve"],
                                      "public-key-type": "rsaEncryption", "public-key-bits": 2048,
                                      "fingerprint": "5D:1D", "pem": "-----BEGIN CERTIFICATE-----SECRET"}],
    "/nodes/pve/hardware/pci": [{"id": "0000:00:02.0", "iommugroup": 0, "vendor_name": "Intel", "device_name": "UHD 630"}],
    "/access/users": [{"userid": "root@pam", "enable": 1, "expire": 0, "realm-type": "pam", "email": "a@example.test",
                       "groups": "admins,ops"},
                      {"userid": "proxorchestrator@pve", "enable": 1, "realm-type": "pve", "tokens": [{"tokenid": "app"}]}],
    "/access/groups": [],
    "/access/acl": [{"path": "/", "ugid": "proxorchestrator@pve", "type": "user", "roleid": "PVEVMAdmin", "propagate": 1}],
    "/access/roles": [{"roleid": "PVEAuditor", "special": 1, "privs": "Sys.Audit,VM.Audit"}],
    "/pools": [],
    "/access/domains": [{"realm": "pam", "type": "pam"}],
}


def fake_get(path, **kw):
    if path not in DATA:
        raise ProxmoxAPIError(f"GET {path} returned HTTP 403", status_code=403)
    return DATA[path]


def _client(admin):
    user = User.objects.create_user("admin" if admin else "op", password="pw-1234567890", is_staff=admin)
    UserProfile.objects.update_or_create(user=user, defaults={"must_change_password": False})
    c = Client()
    c.force_login(user)
    return c


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class NodePagesTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve",
                "api_token_id": "t@pve!x", "api_token_secret": "s"})
        for p in (mock.patch("apps.proxmox.api.ProxmoxAPI._get", side_effect=fake_get),
                  mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value={"/": {"Sys.Audit": 1}})):
            p.start()
            self.addCleanup(p.stop)
        self.admin = _client(True)

    def test_all_node_tabs(self):
        expect = {"services": "PVE API Proxy", "network": "192.0.2.11/24", "dns": "Europe/Rome",
                  "disks": "95%", "updates": "pve-no-subscription", "certificates": "pve.home.arpa",
                  "hardware": "UHD 630"}
        for tab, needle in expect.items():
            r = self.admin.get(f"/node/{tab}/")
            self.assertEqual(r.status_code, 200, tab)
            self.assertContains(r, needle, msg_prefix=tab)
            self.assertContains(r, "Read-only", msg_prefix=tab)
        r = self.admin.get("/node/dns/")
        self.assertContains(r, "&lt;script&gt;")
        r = self.admin.get("/node/certificates/")
        self.assertNotContains(r, "SECRET")
        self.assertContains(r, "rsaEncryption 2048")
        r = self.admin.get("/node/updates/")
        self.assertContains(r, "7.0.14-28-pve")
        self.assertContains(r, "available updates")
        self.assertEqual(self.admin.get("/node/syslog/").status_code, 404)

    def test_smart_only_known_disks(self):
        r = self.admin.get("/node/smart/?disk=/dev/sda")
        self.assertContains(r, "Temperature: 44 Celsius")
        self.assertEqual(self.admin.get("/node/smart/?disk=/etc/shadow").status_code, 404)

    def test_access_tabs(self):
        r = self.admin.get("/pveaccess/users/")
        self.assertContains(r, "admins, ops")
        self.assertContains(r, "not visible")  # root has no token list
        self.assertContains(r, "app")
        self.assertContains(self.admin.get("/pveaccess/acl/"), "PVEVMAdmin")
        self.assertContains(self.admin.get("/pveaccess/roles/"), "Sys.Audit")
        self.assertContains(self.admin.get("/pveaccess/groups/"), "No groups")
        self.assertContains(self.admin.get("/pveaccess/realms/"), "pam")
        self.assertEqual(self.admin.get("/pveaccess/tokens/").status_code, 404)

    def test_non_admin_forbidden(self):
        op = _client(False)
        for path in ("/node/", "/node/disks/", "/node/smart/?disk=/dev/sda", "/pveaccess/", "/pveaccess/acl/"):
            self.assertEqual(op.get(path).status_code, 403, path)
        r = op.get("/tasks/")
        self.assertNotContains(r, "/pveaccess/")

    def test_api_error_shown(self):
        with mock.patch("apps.proxmox.api.ProxmoxAPI._get", side_effect=ProxmoxAPIError("boom")):
            r = self.admin.get("/node/services/")
        self.assertContains(r, "Could not load: boom")
