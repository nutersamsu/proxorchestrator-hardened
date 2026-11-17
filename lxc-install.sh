#!/usr/bin/env bash
# ProxOrchestrator LXC One-Liner Installer
# Runs on the Proxmox VE host — creates a Debian LXC container and installs ProxOrchestrator inside it.
#
# Usage:
#   bash -c "$(wget -qLO - https://github.com/nutersamsu/proxorchestrator-hardened/raw/hardening/lxc-install.sh)"
#
# Or download and run:
#   wget https://github.com/nutersamsu/proxorchestrator-hardened/raw/hardening/lxc-install.sh
#   bash lxc-install.sh
#
# Options:
#   --id <n>         Container ID (default: next available)
#   --hostname <s>   Container hostname (default: proxorchestrator)
#   --storage <s>    Proxmox storage for rootfs (default: auto-detect)
#   --bridge <s>     Network bridge (default: vmbr0)
#   --disk <n>       Rootfs size in GB (default: 16)
#   --ram <n>        RAM in MB (default: 2048)
#   --cores <n>      CPU cores (default: 2)
#   --port <n>       ProxOrchestrator web UI port (default: 8443)
#   --ip <cidr>      Static IP (e.g. 192.168.1.100/24) — default: DHCP
#   --gateway <ip>   Default gateway (required with --ip)
#   --dns <servers>  DNS servers (e.g. "192.168.1.78 8.8.8.8") — default: host DNS
#   --pve-host <ip>  Address the app uses to reach this Proxmox host (default: this host's IP on --bridge)
#   --pve-user <u>   Proxmox user the app's token belongs to (default: proxorchestrator@pve)
#   --no-connect     Only install; do not create the API token / SSH key (do it later in the web wizard)
#   --yes, -y        Do not ask for confirmation
#   --help           Show this help
#
# Requirements:
#   - Must be run on a Proxmox VE host (pveversion must be available)
#   - Internet access for template download and package installation
#
# What it does:
#   1. Downloads a Debian 13 (or 12) LXC template (if not already cached)
#   2. Creates an unprivileged LXC container with sensible defaults
#   3. Enables nesting (required for ProxOrchestrator's SSH/SFTP to Proxmox)
#   4. Starts the container
#   5. Clones the ProxOrchestrator repo inside the container
#   6. Runs install.sh inside the container
#   7. Connects it to this Proxmox host (unless --no-connect):
#      - creates the user proxorchestrator@pve with PVEVMAdmin + PVEDatastoreUser
#        + PVEAuditor on / (and PVESDNUser on /sdn/zones/localnetwork) and an
#        API token for it,
#      - authorises the container's SSH key for root on this host (needed for
#        disk import/export, community scripts and node temperatures),
#      - pins this host's real SSH host keys and API certificate in the app.
#      The web wizard then only asks you to confirm the defaults.
#   8. Prints the access URL and the first-login password
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Colours and formatting
# ---------------------------------------------------------------------------
RD='\033[0;31m'
GN='\033[0;32m'
YW='\033[0;33m'
BL='\033[0;34m'
CY='\033[0;36m'
NC='\033[0m' # No colour

msg()  { echo -e "${GN}[✓]${NC} $1"; }
info() { echo -e "${BL}[i]${NC} $1"; }
warn() { echo -e "${YW}[!]${NC} $1"; }
err()  { echo -e "${RD}[✗]${NC} $1" >&2; }

header() {
    echo ""
    echo -e "${CY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CY}  ⚡ ProxOrchestrator LXC Installer${NC}"
    echo -e "${CY}  Self-hosted Proxmox VM Manager — by ForgedIO${NC}"
    echo -e "${CY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
CT_ID=""
CT_HOSTNAME="proxorchestrator"
CT_STORAGE=""  # Auto-detect if not specified
CT_BRIDGE="vmbr0"
CT_DISK=16
CT_RAM=2048
CT_CORES=2
CT_PORT=8443
CT_IP="dhcp"
CT_GW=""
CT_DNS=""
PVE_HOST=""
PO_USER="proxorchestrator@pve"
DO_CONNECT=1
ASSUME_YES=0
TEMPLATES=("debian-13-standard" "debian-12-standard")
REPO_URL="${PROXORCHESTRATOR_REPO_URL:-https://github.com/nutersamsu/proxorchestrator-hardened.git}"
REPO_BRANCH="${PROXORCHESTRATOR_REPO_BRANCH:-hardening}"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --id)        CT_ID="$2"; shift 2 ;;
        --hostname)  CT_HOSTNAME="$2"; shift 2 ;;
        --storage)   CT_STORAGE="$2"; shift 2 ;;
        --bridge)    CT_BRIDGE="$2"; shift 2 ;;
        --disk)      CT_DISK="$2"; shift 2 ;;
        --ram)       CT_RAM="$2"; shift 2 ;;
        --cores)     CT_CORES="$2"; shift 2 ;;
        --port)      CT_PORT="$2"; shift 2 ;;
        --ip)        CT_IP="$2"; shift 2 ;;
        --gateway)   CT_GW="$2"; shift 2 ;;
        --dns)       CT_DNS="$2"; shift 2 ;;
        --pve-host)  PVE_HOST="$2"; shift 2 ;;
        --pve-user)  PO_USER="$2"; shift 2 ;;
        --no-connect) DO_CONNECT=0; shift ;;
        --yes|-y)    ASSUME_YES=1; shift ;;
        --help|-h)
            echo "Usage: bash $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --id <n>         Container ID (default: next available)"
            echo "  --hostname <s>   Container hostname (default: proxorchestrator)"
            echo "  --storage <s>    Proxmox storage for rootfs (default: auto-detect)"
            echo "  --bridge <s>     Network bridge (default: vmbr0)"
            echo "  --disk <n>       Rootfs size in GB (default: 16)"
            echo "  --ram <n>        RAM in MB (default: 2048)"
            echo "  --cores <n>      CPU cores (default: 2)"
            echo "  --port <n>       ProxOrchestrator web UI port (default: 8443)"
            echo "  --ip <cidr>      Static IP (e.g. 192.168.1.100/24) — default: DHCP"
            echo "  --gateway <ip>   Default gateway (required with --ip)"
            echo "  --dns <servers>  DNS servers (e.g. \"192.168.1.78 8.8.8.8\")"
            echo "  --pve-host <ip>  Address the app uses to reach this host (default: IP on --bridge)"
            echo "  --pve-user <u>   Proxmox user for the app's token (default: proxorchestrator@pve)"
            echo "  --no-connect     Only install; connect to Proxmox later in the web wizard"
            echo "  --yes, -y        Do not ask for confirmation"
            exit 0
            ;;
        *) err "Unknown option: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
header

if [[ "${EUID}" -ne 0 ]]; then
    err "This script must be run as root on the Proxmox VE host."
    exit 1
fi

if ! command -v pveversion &>/dev/null; then
    err "pveversion not found — this script must be run on a Proxmox VE host."
    exit 1
fi

PVE_VERSION=$(pveversion --verbose 2>/dev/null | head -1)
info "Proxmox detected: ${PVE_VERSION}"

# Get next available CT ID if not specified
if [[ -z "${CT_ID}" ]]; then
    CT_ID=$(pvesh get /cluster/nextid 2>/dev/null || echo "100")
    # pvesh returns the ID with quotes sometimes
    CT_ID=$(echo "${CT_ID}" | tr -d '"')
fi
if pct status "${CT_ID}" &>/dev/null || qm status "${CT_ID}" &>/dev/null; then
    err "ID ${CT_ID} is already used by a VM or container. Choose another with --id <n>."
    exit 1
fi

if [[ "${CT_IP}" != "dhcp" && -z "${CT_GW}" ]]; then
    err "--ip needs --gateway too."
    exit 1
fi

if ! ip link show "${CT_BRIDGE}" &>/dev/null; then
    err "Bridge '${CT_BRIDGE}' not found on this host. Choose one with --bridge <name>."
    exit 1
fi

if [[ -z "${PVE_HOST}" ]]; then
    PVE_HOST=$(ip -4 -o addr show dev "${CT_BRIDGE}" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
fi
if [[ ! "${PO_USER}" =~ ^[A-Za-z0-9._-]+@pve$ ]]; then
    err "--pve-user must be a user of the 'pve' realm, e.g. proxorchestrator@pve"
    exit 1
fi
if [[ "${DO_CONNECT}" -eq 1 && -z "${PVE_HOST}" ]]; then
    err "Could not find this host's IPv4 address on ${CT_BRIDGE}. Pass it with --pve-host <ip>."
    exit 1
fi

# Auto-detect storage if not specified — find first active storage that supports rootdir
if [[ -z "${CT_STORAGE}" ]]; then
    # Prefer local-lvm, then local, then first active storage with rootdir content
    for candidate in local-lvm local; do
        if pvesm status -storage "${candidate}" 2>/dev/null | grep -q "active"; then
            CT_STORAGE="${candidate}"
            break
        fi
    done
    # Fallback: first active storage that supports rootdir content
    if [[ -z "${CT_STORAGE}" ]]; then
        CT_STORAGE=$(pvesm status 2>/dev/null | awk 'NR>1 && $3=="active" {print $1; exit}')
    fi
    if [[ -z "${CT_STORAGE}" ]]; then
        err "No active storage found. Specify one with --storage <name>"
        pvesm status 2>/dev/null
        exit 1
    fi
    info "Auto-selected storage: ${CT_STORAGE}"
fi

# Check that the storage exists and is active
if ! pvesm status -storage "${CT_STORAGE}" 2>/dev/null | grep -q "active"; then
    err "Storage '${CT_STORAGE}' not found or inactive. Available storages:"
    pvesm status 2>/dev/null | tail -n +2 | awk '{print "  " $1 " (" $3 ")"}'
    exit 1
fi

# ---------------------------------------------------------------------------
# Summary and confirmation
# ---------------------------------------------------------------------------
echo ""
info "Container ID:   ${CT_ID}  (hostname ${CT_HOSTNAME})"
info "Resources:      ${CT_CORES} cores, ${CT_RAM} MB RAM, ${CT_DISK} GB on ${CT_STORAGE}"
info "Network:        ${CT_BRIDGE}, IP ${CT_IP}${CT_GW:+, gateway ${CT_GW}}"
info "Web UI port:    ${CT_PORT}"
if [[ "${DO_CONNECT}" -eq 1 ]]; then
    info "Connect to:     this host at ${PVE_HOST} (user ${PO_USER}, API token + SSH key created automatically)"
else
    info "Connect to:     later, in the web wizard (--no-connect)"
fi
echo ""
if [[ "${ASSUME_YES}" -ne 1 && -t 0 ]]; then
    read -rp "Continue? [Y/n] " REPLY_OK || true
    if [[ "${REPLY_OK:-y}" =~ ^[Nn] ]]; then
        info "Cancelled — nothing was changed."
        exit 0
    fi
fi

# ---------------------------------------------------------------------------
# Download template
# ---------------------------------------------------------------------------
info "Checking for a Debian template..."

# Proxmox 9 lists templates for several architectures: only take this host's.
HOST_ARCH=$(dpkg --print-architecture 2>/dev/null || echo amd64)

find_template() {
    local t
    for t in "${TEMPLATES[@]}"; do
        pveam available --section system 2>/dev/null \
            | awk -v t="${t}" -v a="_${HOST_ARCH}." '$2 ~ "^"t && index($2, a) {print $2}' \
            | sort -V | tail -1 | grep . && return 0
    done
    return 1
}

# Find the full template name (version varies); refresh the list once if needed
TEMPLATE_FULL=$(find_template || true)
if [[ -z "${TEMPLATE_FULL}" ]]; then
    info "Refreshing the template list (pveam update)..."
    pveam update >/dev/null 2>&1 || true
    TEMPLATE_FULL=$(find_template || true)
fi
if [[ -z "${TEMPLATE_FULL}" ]]; then
    err "No Debian 12/13 template available. Check this host's internet access and run: pveam update"
    exit 1
fi

# Check if already downloaded
TEMPLATE_STORAGE="local"  # Templates are always on local storage
if ! pveam list "${TEMPLATE_STORAGE}" 2>/dev/null | grep -q "${TEMPLATE_FULL}"; then
    info "Downloading template: ${TEMPLATE_FULL}"
    pveam download "${TEMPLATE_STORAGE}" "${TEMPLATE_FULL}"
else
    msg "Template already available: ${TEMPLATE_FULL}"
fi

# ---------------------------------------------------------------------------
# Create LXC container
# ---------------------------------------------------------------------------
info "Creating LXC container ${CT_ID}..."

# Build network string
if [[ "${CT_IP}" == "dhcp" ]]; then
    NET_STR="name=eth0,bridge=${CT_BRIDGE},ip=dhcp"
else
    NET_STR="name=eth0,bridge=${CT_BRIDGE},ip=${CT_IP}"
    if [[ -n "${CT_GW}" ]]; then
        NET_STR="${NET_STR},gw=${CT_GW}"
    fi
fi

PCT_CREATE_ARGS=(
    pct create "${CT_ID}"
    "${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE_FULL}"
    --hostname "${CT_HOSTNAME}"
    --storage "${CT_STORAGE}"
    --rootfs "${CT_STORAGE}:${CT_DISK}"
    --cores "${CT_CORES}"
    --memory "${CT_RAM}"
    --swap 512
    --net0 "${NET_STR}"
    --unprivileged 1
    --features nesting=1
    --onboot 1
    --start 0
)

if [[ -n "${CT_DNS}" ]]; then
    PCT_CREATE_ARGS+=(--nameserver "${CT_DNS}")
fi

"${PCT_CREATE_ARGS[@]}"

msg "Container ${CT_ID} created."

# ---------------------------------------------------------------------------
# Start container
# ---------------------------------------------------------------------------
info "Starting container ${CT_ID}..."
if ! pct start "${CT_ID}"; then
    err "Container ${CT_ID} did not start — removing it again."
    pct destroy "${CT_ID}" --purge >/dev/null 2>&1 || true
    exit 1
fi

# Wait for container to be fully up
info "Waiting for container to be ready..."
sleep 5

# Wait for network (up to 30 seconds)
for i in $(seq 1 30); do
    if pct exec "${CT_ID}" -- ping -c 1 -W 1 github.com &>/dev/null; then
        break
    fi
    sleep 1
done

# Verify network
if ! pct exec "${CT_ID}" -- ping -c 1 -W 2 github.com &>/dev/null; then
    warn "Container cannot reach github.com — check network configuration."
    warn "You may need to configure DNS or check the bridge settings."
fi

msg "Container is running."

# ---------------------------------------------------------------------------
# Install ProxOrchestrator inside the container
# ---------------------------------------------------------------------------
info "Installing ProxOrchestrator inside container ${CT_ID}..."

# Install prerequisites
pct exec "${CT_ID}" -- bash -c "apt-get update -qq && apt-get install -y -qq git sudo curl" >/dev/null 2>&1
msg "Prerequisites installed (git, sudo, curl)."

# Clone the repository
info "Cloning ProxOrchestrator repository..."
pct exec "${CT_ID}" -- bash -c "git clone -b ${REPO_BRANCH} ${REPO_URL} /opt/proxorchestrator-src" 2>&1 | tail -1

# Run install.sh inside the container
info "Running install.sh (this will take a few minutes)..."
echo ""
if ! pct exec "${CT_ID}" -- bash -c "cd /opt/proxorchestrator-src && bash install.sh --port ${CT_PORT}" </dev/null 2>&1; then
    err "install.sh failed inside container ${CT_ID} (see the output above)."
    err "Remove it with: pct stop ${CT_ID}; pct destroy ${CT_ID}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Connect the app to this Proxmox host
# ---------------------------------------------------------------------------
CONNECTED=0
PO_TOKEN="ct${CT_ID}"

connect_to_proxmox() {
    local pubkey secret fp keyfile out roles

    info "Connecting ProxOrchestrator to this Proxmox host (${PVE_HOST})..."

    # 1. Proxmox user + least-privilege roles
    if ! pveum user list --output-format json 2>/dev/null | grep -q "\"${PO_USER}\""; then
        pveum user add "${PO_USER}" --comment "ProxOrchestrator (CT ${CT_ID})" || return 1
    fi
    pveum acl modify / --users "${PO_USER}" --roles PVEVMAdmin,PVEDatastoreUser,PVEAuditor || return 1
    roles=$(pveum role list --output-format json 2>/dev/null || true)
    if grep -q '"PVESDNUser"' <<<"${roles}"; then
        pveum acl modify /sdn/zones/localnetwork --users "${PO_USER}" --roles PVESDNUser 2>/dev/null \
            || warn "Could not grant PVESDNUser on /sdn/zones/localnetwork (VM network bridges may need it)."
    fi
    msg "Proxmox user ${PO_USER} ready (PVEVMAdmin + PVEDatastoreUser + PVEAuditor)."

    # 2. API token (re-created if this CT ID was used before)
    pveum user token remove "${PO_USER}" "${PO_TOKEN}" &>/dev/null || true
    out=$(pveum user token add "${PO_USER}" "${PO_TOKEN}" --privsep 0 \
          --comment "ProxOrchestrator CT ${CT_ID}" --output-format json) || return 1
    secret=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["value"])' <<<"${out}") || return 1
    out=""
    msg "API token ${PO_USER}!${PO_TOKEN} created."

    # 3. Authorise the container's SSH key for root on this host
    pubkey=$(pct exec "${CT_ID}" -- cat /opt/proxorchestrator/.ssh/id_rsa.pub) || return 1
    if [[ "${pubkey}" != ssh-* ]]; then
        err "Unexpected SSH public key in the container."
        return 1
    fi
    touch /root/.ssh/authorized_keys
    if ! grep -qF "$(awk '{print $2}' <<<"${pubkey}")" /root/.ssh/authorized_keys; then
        cp -a /root/.ssh/authorized_keys "/root/authorized_keys.before-proxorchestrator-ct${CT_ID}"
        printf '%s\n' "${pubkey}" >> /root/.ssh/authorized_keys
    fi
    msg "SSH key of the container authorised for root on this host."

    # 4. Real host keys and API certificate (pinned, no trust-on-first-use)
    fp=$(echo | openssl s_client -connect "${PVE_HOST}:8006" 2>/dev/null \
         | openssl x509 -outform DER 2>/dev/null | python3 -c '
import hashlib, sys
der = sys.stdin.buffer.read()
print(hashlib.sha256(der).hexdigest() if der else "")')
    if [[ -z "${fp}" ]]; then
        err "Could not read the API certificate at ${PVE_HOST}:8006."
        return 1
    fi
    keyfile=$(mktemp)
    cat /etc/ssh/ssh_host_*_key.pub > "${keyfile}"
    pct push "${CT_ID}" "${keyfile}" /tmp/pve_host_keys --perms 0644 || { rm -f "${keyfile}"; return 1; }
    rm -f "${keyfile}"

    # 5. Hand everything to the app (secret on stdin, never on a command line)
    if ! printf '%s\n' "${secret}" | pct exec "${CT_ID}" -- sudo -u proxorchestrator \
            DJANGO_SETTINGS_MODULE=proxorchestrator.settings.production \
            /opt/proxorchestrator/venv/bin/python /opt/proxorchestrator/manage.py connect_proxmox \
            --settings=proxorchestrator.settings.production \
            --host "${PVE_HOST}" --token-id "${PO_USER}!${PO_TOKEN}" \
            --api-fingerprint "${fp}" --known-hosts /tmp/pve_host_keys; then
        secret=""
        pct exec "${CT_ID}" -- rm -f /tmp/pve_host_keys
        return 1
    fi
    secret=""
    pct exec "${CT_ID}" -- rm -f /tmp/pve_host_keys
    return 0
}

if [[ "${DO_CONNECT}" -eq 1 ]]; then
    echo ""
    if connect_to_proxmox; then
        CONNECTED=1
        msg "ProxOrchestrator is connected to this Proxmox host."
    else
        warn "Automatic connection failed — finish it in the web wizard instead (steps 1–3)."
    fi
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${CY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GN}  ⚡ ProxOrchestrator installed successfully!${NC}"
echo -e "${CY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Get the container IP
CT_ACTUAL_IP=""
if [[ "${CT_IP}" != "dhcp" ]]; then
    CT_ACTUAL_IP=$(echo "${CT_IP}" | cut -d'/' -f1)
else
    CT_ACTUAL_IP=$(pct exec "${CT_ID}" -- hostname -I 2>/dev/null | awk '{print $1}')
fi

if [[ -n "${CT_ACTUAL_IP}" ]]; then
    echo -e "  Access ProxOrchestrator at: ${GN}https://${CT_ACTUAL_IP}:${CT_PORT}${NC}"
else
    echo -e "  Access ProxOrchestrator at: ${GN}https://<container-ip>:${CT_PORT}${NC}"
    echo -e "  (run 'pct exec ${CT_ID} -- hostname -I' to find the IP)"
fi

echo ""
echo -e "  Container ID:   ${CT_ID}"
echo -e "  Hostname:       ${CT_HOSTNAME}"
CT_ADMIN_PASS=$(pct exec "${CT_ID}" -- awk '/^password:/{print $2}' /root/proxorchestrator-admin-password.txt 2>/dev/null || true)
if [[ -n "${CT_ADMIN_PASS}" ]]; then
    echo -e "  First login:    ${YW}admin / ${CT_ADMIN_PASS}${NC} (random; you'll be required to change it)"
    echo -e "                  also saved in the container at /root/proxorchestrator-admin-password.txt"
else
    echo -e "  First login:    the admin account created by install.sh (see output above)"
fi
echo ""
if [[ "${CONNECTED}" -eq 1 ]]; then
    echo -e "  Proxmox:        ${GN}already connected${NC} — after logging in, just confirm the defaults."
else
    echo -e "  Proxmox:        connect it in the web wizard after logging in."
fi
echo ""
echo -e "  To enter the container:  ${BL}pct enter ${CT_ID}${NC}"
echo -e "  To update ProxOrchestrator:   ${BL}pct exec ${CT_ID} -- bash -c 'cd /opt/proxorchestrator-src && git pull && sudo ./update.sh'${NC}"
echo -e "  To remove everything:    ${BL}pct stop ${CT_ID}; pct destroy ${CT_ID}; pveum user token remove ${PO_USER} ${PO_TOKEN}${NC}"
echo -e "                           and delete the 'proxorchestrator@${CT_HOSTNAME}' line from /root/.ssh/authorized_keys"
echo ""
