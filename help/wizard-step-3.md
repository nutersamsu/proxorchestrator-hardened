# Setup Wizard — Step 3: API Token

ProxOrchestrator communicates with Proxmox VE via its REST API. This requires an API token — a credential separate from any user password, created in Proxmox itself.

## Why an API token, and why not root?

API tokens are the recommended way to integrate with Proxmox. They:
- Can be revoked at any time without changing anyone's password
- Show up clearly in Proxmox audit logs
- Can be limited to the privileges they need

For security, ProxOrchestrator does **not** use a token of `root@pam`. It uses its own user, `proxorchestrator@pve`, with only the roles needed to manage VMs and containers. If the app were ever compromised, the attacker would not get full control of the host.

## Step by step

1. **Open the Proxmox web UI** at `https://YOUR-HOST:8006` and go to **your node → Shell**

2. **Paste the commands** shown on this page (**Copy commands** button). They:
   - create the user `proxorchestrator@pve`
   - give it the roles `PVEVMAdmin`, `PVEDatastoreUser` and `PVEAuditor` on `/`
   - give it `PVESDNUser` on `/sdn/zones/localnetwork` (needed to attach VMs to bridges on Proxmox 8/9)
   - create the token `app` for that user with `--privsep 0` (the token inherits exactly the user's roles, nothing more)

3. **Copy the secret** — the last command prints a table. Copy the `value` row (a UUID). This is the only time Proxmox shows the secret.

4. **Paste it into this page**:
   - Full Token ID: `proxorchestrator@pve!app`
   - Token Secret: the UUID you copied

If the user already exists, the first line just reports it — that is fine. On Proxmox 7 the `/sdn/...` line can be skipped.

## What the token cannot do

On purpose, the token has no `Sys.Modify`, `Sys.PowerMgmt`, `Sys.Syslog` or `Datastore.Allocate`. That is why some pages (node, datacenter firewall, backup jobs, deleting ISOs) are read-only in ProxOrchestrator; do those things in the Proxmox UI.

## Token ID format

The full token ID follows the format `USER@REALM!TOKENID`. With the commands above:
- User: `proxorchestrator@pve`
- Token ID: `app`

So the full token ID is: `proxorchestrator@pve!app`

## Common issues

**"401 Unauthorized"** — The token ID or secret was entered incorrectly. Token secrets are UUIDs in the format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Double-check for typos.

**"403 Forbidden"** — A role is missing. Check that the `pveum acl modify` commands ran without errors, or whether the token was created with `--privsep 1` (then it does not inherit the user's roles). Remove the token and create it again with `--privsep 0`.

**Token secret was not saved** — Remove the token in Proxmox (`pveum user token remove proxorchestrator@pve app`, or Datacenter → Permissions → API Tokens → Remove) and create a new one. The secret cannot be retrieved later.

**API unreachable** — Ensure port 8006 is accessible from the ProxOrchestrator server (verified in step 1, but sometimes firewalls treat API calls differently).
