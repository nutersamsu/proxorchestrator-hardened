# Import VM — Upload Disk Image

This is the first step in importing a VM into Proxmox. You'll upload your disk image file, which ProxOrchestrator will then convert (if needed) and prepare for VM configuration.

## Supported file formats

| Format | Extension | Notes |
|--------|-----------|-------|
| QCOW2  | `.qcow2`  | Native Proxmox format — no conversion needed, fastest path |
| VMDK   | `.vmdk`   | VMware format — automatically converted to qcow2 |
| VHD    | `.vhd`    | Hyper-V VPC format — automatically converted |
| VHDX   | `.vhdx`   | Hyper-V modern format — automatically converted |
| RAW    | `.raw`, `.img` | Raw disk image — converted to qcow2 |
| OVA    | `.ova`    | Open Virtualization Archive — disks extracted and converted |

All non-qcow2 formats are converted using `qemu-img convert -O qcow2` before being transferred to Proxmox.

## How to upload

**Method 1 — Drag and drop:** Drag your disk image file from your file manager onto the dashed drop zone area. The border will highlight blue when you're hovering over it correctly.

**Method 2 — Browse:** Click anywhere in the drop zone to open a file browser. Navigate to and select your disk image file.

Once a file is selected, the filename and size will be displayed, and the "Upload & Continue" button will appear. Click it to begin the upload.

## Large file uploads

For large disk images (10 GB+):
- Ensure your browser tab remains open during the upload
- The progress bar shows real-time upload progress
- Upload speed depends on your network connection to the ProxOrchestrator server
- There is no file size limit imposed by ProxOrchestrator (your server's disk space is the limit)
- If you close the browser, the upload will be interrupted

## OVA files

OVA files are archives containing the VM disks (VMDK), a manifest, and an OVF descriptor. ProxOrchestrator will:
1. Extract the OVA archive
2. Read the OVF descriptor and pre-fill the hardware settings (CPU, memory, firmware, disks)
3. Convert each VMDK disk to qcow2
4. Import **all** disks of the OVA — you review everything on the configure screen

Some appliance OVAs also ship an installation ISO; in that case the configure screen asks for a Proxmox storage to upload it to.

## Common issues

**"File format not supported"** — Only the listed extensions are accepted. If your file uses a different extension but is actually one of these formats, rename it. For example, a `.img` file that is actually a raw disk image can be renamed to `.raw`.

**Upload appears stuck at 0%** — This can happen if the file is very large and is being buffered. Wait a few seconds — if it still doesn't move, check your network connection.

**Upload fails midway** — Usually a network interruption. Re-select the file and upload again. The failed partial upload is automatically cleaned up.

**"Not enough disk space"** — The ProxOrchestrator server's temp directory (configured in wizard step 5) doesn't have enough space. Free up space or change the temp directory to a larger volume.
