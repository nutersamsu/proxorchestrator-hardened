# Tasks

This page is the Proxmox **task history** of the node, the same list you see
under *Node → Task History* in the Proxmox web interface. Every long-running
operation (start, stop, backup, clone, console session, package update…)
creates a task, whoever started it: this app, the Proxmox UI, `qm`/`pct` on the
shell, or a scheduled job.

## Filters

- **VMID**: only tasks of one VM or container.
- **Type**: the task kind (for example *Backup* = `vzdump`, *VM start* = `qmstart`).
- **User**: who started it, e.g. `root@pam` or `proxorchestrator@pve`.
- **Errors only** / **Running only**.

## Task log

Click a task to see its full output. While a task is running the log refreshes
every 2 seconds and a **Stop** button is shown.

The API token can only stop tasks that it started itself. Stopping tasks of
other users needs the `Sys.Modify` privilege, which the recommended token does
not have.

## Recent tasks bar

The bar at the bottom of every page shows the last six tasks and refreshes
every 10 seconds. Click its title to collapse it; the choice is remembered in
this browser.

## Times

Times are shown in the server time zone. Set `TIME_ZONE` in the app's `.env`
(for example `TIME_ZONE=Europe/Rome`) and run `update.sh` to change it.
