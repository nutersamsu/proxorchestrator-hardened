# Storage

All storages of the node with their type, the content they accept and how
full they are. Click a storage (or one of its content tags) to browse it.

## Content types

- **Backups**: vzdump archives (same actions as on the Backups page).
- **ISO images** and **CT templates**: installation media and container templates.
- **VM disks** / **CT volumes**: disk images of guests. A volume whose guest
  no longer exists is marked *orphan?*.
- **Snippets**, **Import**: hook scripts, cloud-init snippets, files for import.

## What you can do

Buttons only appear when the API token has the privilege:

- deleting ISO images, templates and orphan disks needs `Datastore.Allocate`;
- uploading or downloading from a URL needs `Datastore.AllocateTemplate`
  (and `Sys.Modify` for downloads).

The recommended token has neither, so those files are read-only here. Disks
that belong to a guest are managed from the VM or container page.

*Import files* (under Settings) is a different page: it manages the files
uploaded to ProxOrchestrator for VM imports.
