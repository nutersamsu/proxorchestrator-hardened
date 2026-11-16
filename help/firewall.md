# Firewall

The Proxmox firewall has several levels. A packet to a guest is filtered only
when **all** of these are true:

1. the **datacenter** firewall is enabled (Datacenter → Options);
2. the **guest** firewall is enabled (VM/CT → Firewall → Options);
3. the guest's **network card** has the *Firewall* option ticked.

## Levels on this page

- **Datacenter**: options (enable, default input/output policy), rules that
  apply to the whole cluster, aliases and IPSets usable everywhere (`dc/name`).
- **Node**: rules for the Proxmox host itself.
- **Security groups**: named rule sets that a guest inserts with a rule of
  direction *group*.

Changing the datacenter, node and security groups needs the `Sys.Modify`
privilege. The recommended API token does not have it, so these levels are
read-only here. Enabling the datacenter firewall is done in Proxmox: check the
rules first, or you can lock yourself out of the web interface and SSH.

## Guest firewall (VM and container pages)

Editable with the recommended token (`VM.Config.Network`):

- **Options**: enable, input/output policy, log levels, DHCP, NDP, router
  advertisement, MAC and IP filters.
- **Rules**: direction, action (ACCEPT, DROP, REJECT), a *macro* (predefined
  service such as SSH, HTTP, DNS) **or** protocol and ports, source and
  destination (IP, CIDR, range `a-b`, alias or `+ipset`), interface (`net0`…),
  log level and comment. New rules go to the top; the first matching rule wins.
  Use the arrows to reorder.
- **Aliases** and **IPSets** of the guest.

With an input policy of DROP, only what your rules accept reaches the guest.
Add an ACCEPT rule for SSH or the web port **before** enabling it.

If someone else changes the rules at the same time, Proxmox refuses the edit
(the list changed); reload the page and try again.
