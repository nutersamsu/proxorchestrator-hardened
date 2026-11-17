# Container Export Progress

This page shows real-time progress of a container export job. The page auto-polls for updates — no need to refresh manually.

## Pipeline stages

The export runs through several stages:
1. **Snapshot** — Proxmox takes a snapshot of the running container using vzdump
2. **Package** — the backup and configuration metadata are bundled into a `.px` file
3. **Complete** — the package is ready for download

Each stage shows its current status (pending, in progress, or complete) as the job progresses.

## When the export completes

You'll see a success message with options to:
- **Download .px Package** — save the exported file to your computer
- **Back to Container** — return to the container's detail page
- **All Exports** — go to the export/import hub

The package stays on the server for **24 hours** by default (`EXPORT_RETENTION_HOURS` in `.env`). If *Remove the package from this server after I download it* was ticked, it is deleted as soon as one download finishes completely; an interrupted download leaves it in place.

## If the export fails

An error message is shown with the specific failure reason. Common causes:
- **Insufficient storage** — the dump storage doesn't have enough free space for the backup
- **Container locked** — another operation (backup, snapshot) is already running on this container
- **API timeout** — the Proxmox API didn't respond in time; the container may be very large

You can return to the container detail page and try again.
