"""Phase 4: firewall scopes, validation and views."""

from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.models import UserProfile
from apps.firewall import fw
from apps.wizard.models import ProxmoxConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
DIGEST = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
MACROS = {"SSH": "Secure shell", "HTTP": "Web"}
GUEST = fw.Scope("qemu", node="pve", vmid=100)


class ScopeTests(TestCase):
    def test_paths(self):
        self.assertEqual(fw.Scope("cluster").rules_path, "/cluster/firewall/rules")
        self.assertEqual(fw.Scope("group", group="web").rules_path, "/cluster/firewall/groups/web")
        self.assertEqual(fw.Scope("node", node="pve").base, "/nodes/pve/firewall")
        self.assertEqual(GUEST.base, "/nodes/pve/qemu/100/firewall")
        self.assertEqual(GUEST.acl_path, "/vms/100")
        self.assertEqual(GUEST.edit_privilege, "VM.Config.Network")
        self.assertEqual(fw.Scope("cluster").edit_privilege, "Sys.Modify")
        with self.assertRaises(fw.FirewallError):
            fw.Scope("group", group="../x")


class ValidationTests(TestCase):
    def rule(self, **kw):
        data = {"type": "in", "action": "ACCEPT", "enable": "1"}
        data.update(kw)
        return fw.parse_rule_form(data, GUEST, MACROS, ["webgroup"])

    def test_addresses(self):
        ok = ["192.168.1.0/24", "10.0.0.1", "10.0.0.1-10.0.0.9", "!192.168.1.5", "2001:db8::/32",
              "myalias", "dc/office-net", "+blocklist", "+dc/admins", "10.0.0.1,10.0.0.2"]
        for v in ok:
            self.assertTrue(fw.clean_address(v, "x"), v)
        bad = ["10.0.0.1;rm", "999.1.1.1", "10.0.0.1-2001:db8::1", "+set,10.0.0.1", "a b", "1.1.1.1,,2.2.2.2", "x" * 600]
        for v in bad:
            with self.assertRaises(fw.FirewallError, msg=v):
                fw.clean_address(v, "x")

    def test_ports(self):
        self.assertEqual(fw.clean_ports("22, 80:90,https", "p"), "22,80:90,https")
        for v in ("70000", "22;ls", "1:2:3", "a b"):
            with self.assertRaises(fw.FirewallError, msg=v):
                fw.clean_ports(v, "p")

    def test_rule_with_macro(self):
        d = self.rule(macro="SSH", source="192.168.1.0/24", iface="net0", comment="admin", log="info")
        self.assertEqual(d, {"type": "in", "action": "ACCEPT", "enable": 1, "comment": "admin", "macro": "SSH",
                             "source": "192.168.1.0/24", "iface": "net0", "log": "info"})

    def test_rule_proto_ports(self):
        d = self.rule(proto="tcp", dport="80,443", enable="")
        self.assertEqual((d["proto"], d["dport"], d["enable"]), ("tcp", "80,443", 0))

    def test_rule_rejects(self):
        for bad in ({"action": "ALLOW"}, {"type": "fwd"}, {"macro": "Nope"}, {"proto": "xyz"},
                    {"dport": "22"}, {"macro": "SSH", "dport": "22", "proto": "tcp"},
                    {"iface": "eth0"}, {"log": "loud"}, {"comment": "a\nb"},
                    {"proto": "tcp", "icmp-type": "echo-request"}):
            with self.assertRaises(fw.FirewallError, msg=str(bad)):
                self.rule(**bad)

    def test_group_rule(self):
        d = self.rule(type="group", action="webgroup", iface="net0")
        self.assertEqual(d, {"type": "group", "action": "webgroup", "enable": 1, "comment": "", "iface": "net0"})
        with self.assertRaises(fw.FirewallError):
            self.rule(type="group", action="unknown")

    def test_options(self):
        d = fw.parse_options_form({"enable": "1", "policy_in": "DROP", "policy_out": "ACCEPT",
                                   "log_level_in": "info", "dhcp": "1"}, GUEST)
        self.assertEqual(d["enable"], 1)
        self.assertEqual(d["ipfilter"], 0)
        self.assertEqual(d["log_level_out"], "nolog")
        with self.assertRaises(fw.FirewallError):
            fw.parse_options_form({"policy_in": "ALLOW", "policy_out": "ACCEPT"}, GUEST)
        node = fw.parse_options_form({"enable": "1"}, fw.Scope("node", node="pve"))
        self.assertNotIn("policy_in", node)

    def test_alias_ipset(self):
        self.assertEqual(fw.parse_alias_form({"name": "office", "cidr": "192.168.1.0/24"})["cidr"], "192.168.1.0/24")
        for bad in ({"name": "1x", "cidr": "10.0.0.1"}, {"name": "ok", "cidr": "10.0.0.1-10.0.0.2"}):
            with self.assertRaises(fw.FirewallError):
                fw.parse_alias_form(bad)
        self.assertEqual(fw.parse_ipset_entry({"cidr": "my-alias"})["cidr"], "my-alias")
        self.assertEqual(fw.parse_ipset_entry({"cidr": "!10.0.0.0/8", "nomatch": "1"})["nomatch"], 1)
        with self.assertRaises(fw.FirewallError):
            fw.parse_ipset_entry({"cidr": "10.0.0.1-10.0.0.5"})


def _client():
    user = User.objects.create_user("u", password="pw-1234567890", is_staff=True)
    UserProfile.objects.update_or_create(user=user, defaults={"must_change_password": False})
    c = Client()
    c.force_login(user)
    return c


GUEST_PERMS = {"/": {"VM.Config.Network": 1, "Sys.Audit": 1}}


def fake_get(path, **kw):
    if path.endswith("/macros"):
        return [{"macro": m, "descr": d} for m, d in MACROS.items()]
    if path == "/cluster/firewall/groups":
        return [{"group": "webgroup"}]
    if path.endswith("/rules"):
        return [{"pos": 0, "type": "in", "action": "ACCEPT", "macro": "SSH", "enable": 1, "digest": DIGEST},
                {"pos": 1, "type": "in", "action": "DROP", "proto": "tcp", "dport": "23", "comment": "<x>", "digest": DIGEST}]
    if path == "/cluster/firewall/options":
        return {"enable": 0}
    if path.endswith("/options"):
        return {"enable": 1, "policy_in": "DROP", "digest": DIGEST}
    if path.endswith("/aliases"):
        return [{"name": "office", "cidr": "192.168.1.0/24"}]
    if path.endswith("/ipset"):
        return [{"name": "admins"}]
    if "/ipset/" in path:
        return [{"cidr": "10.0.0.5"}]
    if path.endswith("/config"):
        return {"net0": "virtio=AA,bridge=vmbr0", "net1": "virtio=BB,bridge=vmbr0,firewall=1"}
    return {}


@override_settings(CACHES=LOCMEM, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class ViewTests(TestCase):
    def setUp(self):
        cache.clear()
        with mock.patch("apps.core.nginx_helper._run"):
            ProxmoxConfig.objects.update_or_create(pk=1, defaults={
                "host": "192.0.2.10", "is_configured": True, "default_node": "pve",
                "api_token_id": "t@pve!x", "api_token_secret": "s"})
        self.c = _client()
        for p in (mock.patch("apps.proxmox.api.ProxmoxAPI._get", side_effect=fake_get),
                  mock.patch("apps.proxmox.api.ProxmoxAPI.get_permissions", return_value=GUEST_PERMS)):
            p.start()
            self.addCleanup(p.stop)

    def test_guest_panel(self):
        r = self.c.get("/firewall/vm-100/panel/?next=/vm/100/%23firewall")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "datacenter firewall is off")
        self.assertContains(r, "<strong>net0</strong>")
        self.assertContains(r, "&lt;x&gt;")
        self.assertContains(r, "fw-vm-100-rule-modal")
        self.assertContains(r, 'value="/vm/100/#firewall"')
        self.assertContains(r, "+admins")

    def test_dc_panel_read_only(self):
        r = self.c.get("/firewall/dc/panel/")
        self.assertContains(r, "Read-only")
        self.assertNotContains(r, "fw-dc-rule-modal")

    def test_bad_scope(self):
        for key in ("vm-1", "ct-abc", "group-..", "evil"):
            self.assertEqual(self.c.get(f"/firewall/{key}/panel/").status_code, 404, key)

    def test_unsafe_next_ignored(self):
        r = self.c.get("/firewall/vm-100/panel/?next=//evil.example/")
        self.assertContains(r, 'value="/firewall/"')

    @mock.patch("apps.proxmox.api.ProxmoxAPI._post")
    def test_rule_add(self, post):
        r = self.c.post("/firewall/vm-100/rules/add/", {"type": "in", "action": "ACCEPT", "macro": "HTTP",
                                                        "enable": "1", "next": "/vm/100/#firewall"})
        self.assertEqual(r["Location"], "/vm/100/#firewall")
        post.assert_called_once_with("/nodes/pve/qemu/100/firewall/rules",
                                     {"type": "in", "enable": 1, "comment": "", "action": "ACCEPT", "macro": "HTTP"})

    @mock.patch("apps.proxmox.api.ProxmoxAPI._post")
    def test_rule_add_invalid_not_sent(self, post):
        self.c.post("/firewall/vm-100/rules/add/", {"type": "in", "action": "ACCEPT", "source": "1.1.1.1;rm -rf"})
        post.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI._put")
    def test_rule_edit_removes_empty_fields_and_sends_digest(self, put):
        self.c.post("/firewall/ct-101/rules/1/edit/", {"type": "in", "action": "DROP", "proto": "tcp", "dport": "23",
                                                       "enable": "1", "digest": DIGEST})
        path, data = put.call_args.args
        self.assertEqual(path, "/nodes/pve/lxc/101/firewall/rules/1")
        self.assertEqual(data["digest"], DIGEST)
        self.assertIn("macro", data["delete"])
        self.assertNotIn("dport", data["delete"])

    @mock.patch("apps.proxmox.api.ProxmoxAPI._delete")
    def test_rule_delete_bad_digest_404(self, delete):
        self.assertEqual(self.c.post("/firewall/vm-100/rules/0/delete/", {"digest": "x;y"}).status_code, 404)
        self.c.post("/firewall/vm-100/rules/0/delete/", {"digest": DIGEST})
        delete.assert_called_once_with(f"/nodes/pve/qemu/100/firewall/rules/0?digest={DIGEST}")

    @mock.patch("apps.proxmox.api.ProxmoxAPI._put")
    def test_move_and_toggle(self, put):
        self.c.post("/firewall/vm-100/rules/1/move/", {"moveto": "0"})
        put.assert_called_with("/nodes/pve/qemu/100/firewall/rules/1", {"moveto": 0})
        self.c.post("/firewall/vm-100/rules/1/toggle/", {"enable": "0"})
        put.assert_called_with("/nodes/pve/qemu/100/firewall/rules/1", {"enable": 0})

    @mock.patch("apps.proxmox.api.ProxmoxAPI._put")
    def test_cluster_write_refused_without_sys_modify(self, put):
        self.c.post("/firewall/dc/options/", {"enable": "1", "policy_in": "DROP", "policy_out": "ACCEPT"})
        self.c.post("/firewall/node/rules/0/toggle/", {"enable": "0"})
        put.assert_not_called()

    @mock.patch("apps.proxmox.api.ProxmoxAPI._delete")
    @mock.patch("apps.proxmox.api.ProxmoxAPI._post")
    def test_aliases_and_ipsets(self, post, delete):
        self.c.post("/firewall/vm-100/aliases/add/", {"name": "office", "cidr": "192.168.1.0/24"})
        post.assert_called_with("/nodes/pve/qemu/100/firewall/aliases",
                                {"name": "office", "cidr": "192.168.1.0/24", "comment": ""})
        self.c.post("/firewall/vm-100/ipset/admins/entry/add/", {"cidr": "10.0.0.0/8"})
        post.assert_called_with("/nodes/pve/qemu/100/firewall/ipset/admins", {"cidr": "10.0.0.0/8", "comment": ""})
        self.c.post("/firewall/vm-100/ipset/admins/entry/remove/", {"cidr": "10.0.0.0/8"})
        delete.assert_called_with("/nodes/pve/qemu/100/firewall/ipset/admins/10.0.0.0%2F8")
        self.assertEqual(self.c.post("/firewall/node/aliases/add/", {"name": "x1", "cidr": "1.1.1.1"}).status_code, 404)

    def test_index(self):
        r = self.c.get("/firewall/")
        self.assertContains(r, "webgroup")
        self.assertContains(r, "Creating groups needs")
