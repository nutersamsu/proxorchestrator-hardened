"""Proxmox firewall: scopes, API paths and strict validation of rules/options.

One code path serves every level of the PVE firewall:
  cluster  /cluster/firewall
  group    /cluster/firewall/groups/<name>      (rules only)
  node     /nodes/<node>/firewall
  qemu/lxc /nodes/<node>/<kind>/<vmid>/firewall
"""

import ipaddress
import re
from urllib.parse import quote

ACTIONS = ("ACCEPT", "DROP", "REJECT")
DIRECTIONS = ("in", "out", "group")
POLICIES = ("ACCEPT", "DROP", "REJECT")
LOG_LEVELS = ("nolog", "emerg", "alert", "crit", "err", "warning", "notice", "info", "debug")
PROTOCOLS = ("tcp", "udp", "icmp", "icmpv6", "ipv6-icmp", "igmp", "gre", "esp", "ah", "sctp", "udplite",
             "ospf", "vrrp", "pim", "ipv6", "ipip", "l2tp")

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")
GROUP_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,17}$")
IFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,19}$")
PORT_ITEM_RE = re.compile(r"^([0-9]{1,5}(:[0-9]{1,5})?|[a-z][a-z0-9-]{0,30})$")
ALIAS_REF_RE = re.compile(r"^(dc/|guest/)?[A-Za-z][A-Za-z0-9_-]{1,63}$")
IPSET_REF_RE = re.compile(r"^\+(dc/|guest/)?[A-Za-z][A-Za-z0-9_-]{1,63}$")
MACRO_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")


class FirewallError(ValueError):
    pass


class Scope:
    def __init__(self, kind, node=None, vmid=None, group=None):
        if kind not in ("cluster", "group", "node", "qemu", "lxc"):
            raise FirewallError("Unknown firewall scope.")
        if kind == "group" and not (group and GROUP_RE.match(group)):
            raise FirewallError("Invalid security group name.")
        self.kind, self.node, self.vmid, self.group = kind, node, vmid, group

    @property
    def base(self):
        if self.kind == "cluster":
            return "/cluster/firewall"
        if self.kind == "group":
            return f"/cluster/firewall/groups/{quote(self.group, safe='')}"
        if self.kind == "node":
            return f"/nodes/{self.node}/firewall"
        return f"/nodes/{self.node}/{self.kind}/{int(self.vmid)}/firewall"

    @property
    def rules_path(self):
        return self.base if self.kind == "group" else f"{self.base}/rules"

    @property
    def acl_path(self):
        if self.kind in ("qemu", "lxc"):
            return f"/vms/{int(self.vmid)}"
        if self.kind == "node":
            return f"/nodes/{self.node}"
        return "/"

    @property
    def edit_privilege(self):
        return "VM.Config.Network" if self.kind in ("qemu", "lxc") else "Sys.Modify"

    @property
    def has_options(self):
        return self.kind != "group"

    @property
    def has_objects(self):
        """Aliases and IPSets exist at cluster and guest level."""
        return self.kind in ("cluster", "qemu", "lxc")

    @property
    def label(self):
        return {"cluster": "Datacenter", "group": f"Security group {self.group}", "node": f"Node {self.node}",
                "qemu": f"VM {self.vmid}", "lxc": f"CT {self.vmid}"}[self.kind]


# ---------------------------------------------------------------------------
# Validation of address / port fields
# ---------------------------------------------------------------------------

def _addr_item(item):
    if IPSET_REF_RE.match(item) or ALIAS_REF_RE.match(item):
        return True
    if "-" in item:
        a, _, b = item.partition("-")
        try:
            return ipaddress.ip_address(a).version == ipaddress.ip_address(b).version
        except ValueError:
            return False
    try:
        ipaddress.ip_network(item, strict=False)
        return True
    except ValueError:
        return False


def clean_address(value, label):
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) > 512:
        raise FirewallError(f"{label}: too long.")
    body = value[1:] if value.startswith("!") else value
    items = [i.strip() for i in body.split(",")]
    if not items or not all(items) or not all(_addr_item(i) for i in items):
        raise FirewallError(f"{label}: use IPs, networks (CIDR), ranges (a-b), an alias or +ipset, comma separated.")
    if any(IPSET_REF_RE.match(i) for i in items) and len(items) > 1:
        raise FirewallError(f"{label}: an IPSet cannot be combined with other entries.")
    return ("!" if value.startswith("!") else "") + ",".join(items)


def clean_ports(value, label):
    value = (value or "").strip()
    if not value:
        return ""
    body = value[1:] if value.startswith("!") else value
    items = [i.strip() for i in body.split(",")]
    for i in items:
        if not PORT_ITEM_RE.match(i):
            raise FirewallError(f"{label}: ports like 22, 8000:8100 or a service name, comma separated.")
        nums = [int(n) for n in i.split(":") if n.isdigit()]
        if any(n > 65535 for n in nums):
            raise FirewallError(f"{label}: port numbers go up to 65535.")
    return ("!" if value.startswith("!") else "") + ",".join(items)


def _one_line(value, label, limit=255):
    value = (value or "").strip()
    if len(value) > limit or any(c in value for c in "\r\n\x00"):
        raise FirewallError(f"{label}: one line, up to {limit} characters.")
    return value


# ---------------------------------------------------------------------------
# Rules, options, aliases, ipsets
# ---------------------------------------------------------------------------

def parse_rule_form(post, scope, macros, groups):
    """Return the body for POST/PUT …/rules."""
    data = {}
    direction = post.get("type", "in")
    if direction not in DIRECTIONS or (direction == "group" and scope.kind == "group"):
        raise FirewallError("Unknown direction.")
    data["type"] = direction
    data["enable"] = 1 if post.get("enable") == "1" else 0
    data["comment"] = _one_line(post.get("comment"), "Comment")

    if direction == "group":
        group = post.get("action", "")
        if group not in groups:
            raise FirewallError("Choose an existing security group.")
        data["action"] = group
        iface = (post.get("iface") or "").strip()
        if iface:
            if not IFACE_RE.match(iface):
                raise FirewallError("Invalid interface name.")
            data["iface"] = iface
        return data

    action = post.get("action", "")
    if action not in ACTIONS:
        raise FirewallError("Action must be ACCEPT, DROP or REJECT.")
    data["action"] = action
    macro = (post.get("macro") or "").strip()
    if macro:
        if not MACRO_RE.match(macro) or macro not in macros:
            raise FirewallError("Unknown macro.")
        data["macro"] = macro
    proto = (post.get("proto") or "").strip().lower()
    if proto:
        if not (proto in PROTOCOLS or (proto.isdigit() and int(proto) <= 255)):
            raise FirewallError("Unknown protocol.")
        if macro:
            raise FirewallError("A macro already defines the protocol and ports; leave them empty.")
        data["proto"] = proto
    for key, label in (("source", "Source"), ("dest", "Destination")):
        v = clean_address(post.get(key), label)
        if v:
            data[key] = v
    for key, label in (("sport", "Source port"), ("dport", "Destination port")):
        v = clean_ports(post.get(key), label)
        if v:
            if macro:
                raise FirewallError("A macro already defines the protocol and ports; leave them empty.")
            if proto not in ("tcp", "udp", "sctp", "udplite"):
                raise FirewallError("Ports need the protocol tcp, udp, sctp or udplite.")
            data[key] = v
    icmp = (post.get("icmp-type") or "").strip()
    if icmp:
        if proto not in ("icmp", "icmpv6", "ipv6-icmp") or not re.match(r"^[a-z0-9-]{1,40}$", icmp):
            raise FirewallError("ICMP type needs protocol icmp/icmpv6 and a name like echo-request.")
        data["icmp-type"] = icmp
    iface = (post.get("iface") or "").strip()
    if iface:
        if not IFACE_RE.match(iface):
            raise FirewallError("Invalid interface name.")
        if scope.kind in ("qemu", "lxc") and not re.match(r"^net\d+$", iface):
            raise FirewallError("On a guest the interface is net0, net1, …")
        data["iface"] = iface
    log = post.get("log", "nolog") or "nolog"
    if log not in LOG_LEVELS:
        raise FirewallError("Unknown log level.")
    if log != "nolog":
        data["log"] = log
    return data


GUEST_OPTION_BOOLS = ("enable", "dhcp", "ndp", "radv", "macfilter", "ipfilter")
CLUSTER_OPTION_BOOLS = ("enable", "ebtables")
NODE_OPTION_BOOLS = ("enable", "ndp", "nosmurfs", "tcpflags")


def parse_options_form(post, scope):
    if scope.kind in ("qemu", "lxc"):
        bools = GUEST_OPTION_BOOLS
    elif scope.kind == "cluster":
        bools = CLUSTER_OPTION_BOOLS
    else:
        bools = NODE_OPTION_BOOLS
    data = {k: (1 if post.get(k) == "1" else 0) for k in bools}
    if scope.kind in ("qemu", "lxc", "cluster"):
        for k in ("policy_in", "policy_out"):
            v = post.get(k, "")
            if v not in POLICIES:
                raise FirewallError("Policy must be ACCEPT, DROP or REJECT.")
            data[k] = v
    if scope.kind in ("qemu", "lxc", "node"):
        for k in ("log_level_in", "log_level_out"):
            v = post.get(k, "nolog") or "nolog"
            if v not in LOG_LEVELS:
                raise FirewallError("Unknown log level.")
            data[k] = v
    return data


def parse_alias_form(post):
    name = (post.get("name") or "").strip()
    if not NAME_RE.match(name):
        raise FirewallError("Alias name: letters, digits, _ and - (starts with a letter).")
    cidr = (post.get("cidr") or "").strip()
    try:
        ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        raise FirewallError("Alias value must be an IP address or network (CIDR).")
    return {"name": name, "cidr": cidr, "comment": _one_line(post.get("comment"), "Comment")}


def parse_ipset_form(post):
    name = (post.get("name") or "").strip()
    if not NAME_RE.match(name):
        raise FirewallError("IPSet name: letters, digits, _ and - (starts with a letter).")
    return {"name": name, "comment": _one_line(post.get("comment"), "Comment")}


def parse_ipset_entry(post):
    cidr = (post.get("cidr") or "").strip()
    body = cidr[1:] if cidr.startswith("!") else cidr
    is_alias = bool(ALIAS_REF_RE.match(body))
    is_net = False
    if not is_alias:
        try:
            ipaddress.ip_network(body, strict=False)
            is_net = True
        except ValueError:
            pass
    if not (is_alias or is_net):
        raise FirewallError("Entry must be an IP, a network (CIDR) or an alias.")
    data = {"cidr": cidr, "comment": _one_line(post.get("comment"), "Comment")}
    if post.get("nomatch") == "1":
        data["nomatch"] = 1
    return data


def rule_summary(rule):
    """Short text for the rules table."""
    if rule.get("type") == "group":
        return f"group {rule.get('action')}"
    parts = [rule.get("macro") or rule.get("proto") or "any"]
    if rule.get("dport"):
        parts.append(f"dport {rule['dport']}")
    if rule.get("sport"):
        parts.append(f"sport {rule['sport']}")
    if rule.get("icmp-type"):
        parts.append(rule["icmp-type"])
    return " ".join(parts)
