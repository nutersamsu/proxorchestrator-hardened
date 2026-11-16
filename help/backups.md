# Backups

Backups are Proxmox **vzdump** archives (`vzdump-qemu-…` for VMs,
`vzdump-lxc-…` for containers) kept on storages that accept the *backup*
content type.

## Backup jobs

The scheduled jobs from *Datacenter → Backup* in Proxmox: schedule, next run,
which guests, storage, mode and retention.

- **Run now** starts the job immediately with the same settings, as in the
  Proxmox UI. A job **hook script** is not run this way: only `root@pam` may
  set the `script` option.
- Creating or editing jobs needs the `Sys.Modify` privilege. The recommended
  API token does not have it, so jobs are read-only here.

## Backup now

Choose one or more guests, a storage, the mode and the compression:

- **Snapshot**: the guest keeps running (recommended).
- **Suspend**: the guest is paused during the backup.
- **Stop**: the guest is shut down, backed up and started again.

The notes accept `{{guestname}}`, `{{vmid}}` and `{{node}}`. A **protected**
backup is never removed by retention rules and cannot be deleted until the
protection is removed.

Each VM and container page also has a **Backup** card with its own backups
and a *Backup now* button.

## Restore

The restore page shows the configuration stored in the archive. You can:

- restore to a **new ID** (the default when the original guest still exists;
  tick *Unique* so the copy gets new MAC addresses), or
- **overwrite** the original guest: tick *Overwrite* and type the ID again.
  The guest must be stopped; its current disks are destroyed.

The disks go to the storage they came from unless you choose another one.

## Deleting

Delete asks you to type the file name. Protected backups must be unprotected
first. Proxmox lets the API token delete a backup when it has `VM.Backup` on
that guest and space allocation rights on the storage.
