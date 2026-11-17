"""Connect ProxOrchestrator to a Proxmox host without the manual wizard steps.

Used by lxc-install.sh, which runs on the Proxmox host itself and therefore
knows the real SSH host keys and API certificate (no trust-on-first-use) and
can create the API token. The token secret is read from standard input so it
never appears in a process list.

    printf '%s\\n' "$SECRET" | manage.py connect_proxmox \\
        --host 192.168.1.5 --token-id 'proxorchestrator@pve!ct120' \\
        --api-fingerprint <sha256 hex> --known-hosts /tmp/pve_host_keys

Afterwards the wizard opens directly on step 5 (defaults), pre-filled with
what discovery found.
"""

import os
import re
import sys

import paramiko
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from apps.proxmox import hostkeys
from apps.proxmox import tlspin
from apps.proxmox.api import ProxmoxAPIError
from apps.wizard.discovery import run_discovery
from apps.wizard.models import ProxmoxConfig

TOKEN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+![A-Za-z][A-Za-z0-9._-]*$")


def pin_api_fingerprint(host, port, fingerprint):
    fp = fingerprint.replace(":", "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fp):
        raise CommandError("--api-fingerprint must be a SHA-256 hex digest")
    key = f"{host}:{int(port)}"
    with tlspin._lock:
        data = tlspin._load()
        data[key] = fp
        tlspin._save(data)
    return fp


def pin_ssh_host_keys(host, port, lines):
    """Pin the given public host keys ("type base64" or "host type base64")."""
    entry_name = host if int(port) == 22 else f"[{host}]:{port}"
    path = hostkeys.known_hosts_path()
    added = 0
    with hostkeys._lock:
        keys = paramiko.HostKeys()
        if os.path.exists(path):
            keys.load(path)
        if entry_name in keys:
            del keys[entry_name]
        for raw in lines:
            parts = raw.split()
            if len(parts) >= 3 and not parts[0].startswith(("ssh-", "ecdsa-")):
                parts = parts[1:]
            if len(parts) < 2:
                continue
            entry = paramiko.hostkeys.HostKeyEntry.from_line(f"{entry_name} {parts[0]} {parts[1]}")
            if entry is None:
                continue
            keys.add(entry_name, entry.key.get_name(), entry.key)
            added += 1
        if not added:
            raise CommandError("no valid SSH host key in --known-hosts")
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        keys.save(path)
        os.chmod(path, 0o600)
    return added


class Command(BaseCommand):
    help = "Connect to a Proxmox host non-interactively (token secret on stdin)."

    def add_arguments(self, parser):
        parser.add_argument("--host", required=True)
        parser.add_argument("--api-port", type=int, default=8006)
        parser.add_argument("--ssh-port", type=int, default=22)
        parser.add_argument("--token-id", required=True)
        parser.add_argument("--api-fingerprint", default="",
                            help="SHA-256 of the API certificate (pinned instead of trust-on-first-use)")
        parser.add_argument("--known-hosts", default="",
                            help="file with the host's SSH public keys (pinned instead of trust-on-first-use)")

    def handle(self, *args, **opts):
        host = opts["host"].strip()
        token_id = opts["token_id"].strip()
        if not re.fullmatch(r"[A-Za-z0-9.:\-\[\]]+", host):
            raise CommandError("invalid --host")
        if not TOKEN_ID_RE.match(token_id):
            raise CommandError("--token-id must look like user@realm!name")

        secret = sys.stdin.readline().strip()
        if not secret:
            raise CommandError("token secret expected on standard input")

        if opts["api_fingerprint"]:
            pin_api_fingerprint(host, opts["api_port"], opts["api_fingerprint"])
            self.stdout.write("API certificate pinned.")
        if opts["known_hosts"]:
            with open(opts["known_hosts"], encoding="utf-8") as fh:
                n = pin_ssh_host_keys(host, opts["ssh_port"], fh.read().splitlines())
            self.stdout.write(f"SSH host keys pinned ({n}).")

        config = ProxmoxConfig.objects.first() or ProxmoxConfig()
        config.host = host
        config.api_port = opts["api_port"]
        config.ssh_port = opts["ssh_port"]
        config.api_token_id = token_id
        config.api_token_secret = secret

        try:
            nodes = config.get_api_client().get_nodes()
        except ProxmoxAPIError as exc:
            raise CommandError(f"Proxmox API check failed: {exc.message}")
        if not nodes:
            raise CommandError("API token works but no nodes were returned")
        self.stdout.write(f"API token OK (node: {nodes[0].get('node', '?')}).")

        try:
            with config.get_ssh_client() as ssh:
                ssh.run_checked(["echo", "proxorchestrator-ok"])
        except Exception as exc:
            raise CommandError(f"SSH check failed: {exc}")
        self.stdout.write("SSH key login OK.")

        config.wizard_step = max(config.wizard_step or 1, 4)
        config.save()

        try:
            run_discovery(config)
        except Exception as exc:
            raise CommandError(f"Discovery failed: {exc}")

        self.stdout.write(self.style.SUCCESS(
            "Connected. The setup wizard will open on step 5 (review defaults)."))
