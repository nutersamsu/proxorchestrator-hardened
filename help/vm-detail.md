# VM Detail

This page shows the complete configuration of a single Proxmox VM, fetched live from the Proxmox API. You can also control the VM's power state from the page header.

## Power actions

The action buttons shown in the top-right depend on the VM's current status:

- **Shutdown** (running VMs) — Graceful ACPI shutdown. The guest OS will save data and power off cleanly. May take 30–60 seconds to complete.
- **Force Stop** (running VMs) — Immediate power cut. Use only when the VM is frozen and won't respond to a graceful shutdown. Risk of data loss.
- **Reboot** (running VMs) — Graceful restart via ACPI reboot signal.
- **More** (running VMs):
  - **Reset** — hard reset, like pressing the reset button. No clean shutdown.
  - **Pause** — freezes the VM in RAM. **Resume** continues it.
  - **Hibernate** — saves the RAM to disk and stops the VM. **Start** resumes it where it was.
- **Start** (stopped VMs) — Boot the VM (or resume a hibernated one).
- **Resume** (paused VMs) — Continue a paused VM.
- **Convert to template** (stopped VMs) — turns the VM into a template. Templates cannot be started; create new VMs from them with **Clone** (a linked clone is instant and shares the template's disks). Cannot be undone here.

After clicking an action, the status banner will update. The VM may take a few seconds to change state — refresh the page if the status doesn't update.

## Status banner

The colored banner at the top shows the VM's current state:
- **Green** — Running, with live CPU and RAM usage shown
- **Red** — Stopped
- **Yellow** — Paused/suspended

Running VMs show real-time CPU utilization percentage and current memory usage alongside uptime.

## Configuration sections

### General
Basic VM properties: VMID, name, OS type, and description. Use **Rename VM** to change the name and the pencil next to the description to edit the notes (Markdown, as in Proxmox).

### Firmware & Boot
Shows the BIOS type (SeaBIOS or OVMF), whether an EFI disk and TPM are configured, boot order, and start-on-boot status.

**BIOS type mismatch** — If a VM fails to boot after import, double-check that the BIOS type here matches what the original VM used. A UEFI VM with SeaBIOS configured won't boot correctly.

### CPU
Shows CPU type, sockets, cores, and total vCPU count. A VM configured with 2 sockets × 4 cores = 8 total vCPUs.

**Performance tip:** Fewer sockets with more cores is generally more efficient than many sockets with few cores. The guest OS sees the same total vCPU count either way.

### Memory
Shows configured RAM and balloon settings. Ballooning allows Proxmox to dynamically reclaim unused memory from VMs when the host is under memory pressure.

### Disks
A table of all disk devices attached to the VM:
- **Interface** — `scsi0`, `ide0`, `sata0`, `virtio0`, etc.
- **Storage** — Which Proxmox storage pool the disk lives on
- **Size** — Disk size
- **Format** — `qcow2`, `raw`, etc.

If you imported the VM with ProxOrchestrator, the primary disk should be `scsi0` (or `ide0` if you chose IDE during configuration) and format `qcow2`.

### Network Interfaces
Shows all NICs, their model, bridge, MAC address, and VLAN tag. If a VM isn't getting network access, verify the bridge shown here matches your physical network setup in Proxmox.

**Move** copies a disk to another storage (optionally converting it to qcow2/raw) and can delete the source afterwards. It works while the VM runs; the progress opens in the task log.

### Options
The Proxmox *Options* tab: OS type, QEMU guest agent, protection, hotplug, tablet pointer, ACPI, KVM, RTC in local time, freeze CPU at startup, tags, display (VGA type and memory) and the SCSI controller. Only the values you change are sent to Proxmox.

**Start/shutdown order** needs the `Sys.Modify` privilege. With the recommended API token it is shown read-only.

### Display & other hardware
Display type, SCSI controller, machine type and devices the app does not edit (USB/PCI passthrough, serial ports, audio, RNG…). Adding passthrough devices needs root or resource mappings in Proxmox.

### Guest agent
Shown for running VMs with the agent enabled: operating system, host name, all IP addresses and file system usage, read from the QEMU guest agent inside the VM.

### Cloud-Init
User, password, SSH keys, DNS and the IP configuration of each network interface. Without a cloud-init drive, the card offers to add one. Values reach the guest only after **Regenerate image** and a boot; the card lists values that are not in the image yet.

### Performance
CPU, memory, network and disk graphs (hour to year, average or maximum).

## Console

**Console** (running VMs) opens the noVNC console in a new tab.
