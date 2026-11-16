# Node

Details of the Proxmox host, as in the *Node* section of the Proxmox UI.
Only ProxOrchestrator administrators can open this page.

- **Services**: Proxmox and system services with their state. *dead* is
  normal for services a single node does not use (corosync) or that another
  service replaces (systemd-timesyncd when chrony runs).
- **Network**: bridges, bonds, VLANs and network cards with addresses and
  gateway.
- **DNS, hosts & time**: DNS servers, search domain, `/etc/hosts`, time zone.
- **Disks**: physical disks with S.M.A.R.T. health and SSD wearout
  (*Show S.M.A.R.T.* for all attributes), LVM volume groups, LVM-thin pools
  (data and metadata usage), ZFS pools and directory mounts.
- **Repositories & packages**: subscription, enabled Proxmox repositories,
  APT sources and the installed versions of the main packages.
- **Certificates**: the node certificates with expiry date and fingerprint.
- **PCI devices**: devices and IOMMU groups (for PCI passthrough).

## Read-only

Changing the node — restarting services, editing the network or DNS,
installing updates, rebooting — needs `Sys.Modify` / `Sys.PowerMgmt`, and the
list of available updates and the system log need `Sys.Modify` /
`Sys.Syslog`. The recommended API token has none of them on purpose; do these
things in the Proxmox UI.
