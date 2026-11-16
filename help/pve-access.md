# Proxmox permissions

The users, groups and permissions **of Proxmox** (Datacenter → Permissions),
not the accounts of ProxOrchestrator (those are under *Account → Users*).
Only ProxOrchestrator administrators can open this page.

- **Users**: realm, enabled, expiry, name, e-mail, groups and API tokens
  (tokens of other users are only listed when the API token may see them).
- **Groups** and their members.
- **Permissions**: the ACL — which user, group or token has which role on
  which path (`/`, `/vms/100`, `/storage/local`…). *Propagate* means the role
  also applies below that path.
- **Roles**: built-in and custom roles with their privileges.
- **Pools**: resource pools and their members.
- **Realms**: authentication sources (PAM, Proxmox VE, LDAP, OpenID…).

Use this page to check what the ProxOrchestrator token (`proxorchestrator@pve!app`)
is allowed to do. Changing users and ACLs needs `User.Modify` /
`Permissions.Modify`; do it in the Proxmox UI.
