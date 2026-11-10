"""SSH host-key pinning for the Proxmox host (trust on first use).

The first successful connection — normally the setup wizard, when the
administrator types the root password — records the host key in
settings.SSH_KNOWN_HOSTS. From then on a different key makes paramiko raise
BadHostKeyException instead of silently trusting a possible
man-in-the-middle (the previous AutoAddPolicy accepted any key every time).

If the Proxmox host is legitimately reinstalled, forget the old key with:
    python manage.py forget_proxmox_hostkey <host> [--port 22]
"""

import logging
import os
import threading

import paramiko
from django.conf import settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def known_hosts_path():
    return getattr(settings, "SSH_KNOWN_HOSTS", "/opt/proxorchestrator/.ssh/known_hosts")


class TrustOnFirstUsePolicy(paramiko.MissingHostKeyPolicy):
    """Record an unknown host's key once; known hosts are checked strictly."""

    def missing_host_key(self, client, hostname, key):
        path = known_hosts_path()
        with _lock:
            # Re-read in case another worker pinned it meanwhile.
            current = paramiko.HostKeys()
            if os.path.exists(path):
                current.load(path)
            pinned = current.lookup(hostname)
            if pinned:
                stored = pinned.get(key.get_name())
                if stored is None or stored != key:
                    raise paramiko.BadHostKeyException(
                        hostname, key, stored or next(iter(pinned.values()))
                    )
                return
            current.add(hostname, key.get_name(), key)
            os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
            current.save(path)
            os.chmod(path, 0o600)
        logger.warning(
            "Pinned SSH host key for %s: %s %s",
            hostname, key.get_name(), key.fingerprint,
        )


def prepare_client(client):
    """Configure a paramiko SSHClient with pinned host keys."""
    path = known_hosts_path()
    if os.path.exists(path):
        client.load_host_keys(path)
    client.set_missing_host_key_policy(TrustOnFirstUsePolicy())
    return client


def forget(hostname, port=22):
    path = known_hosts_path()
    if not os.path.exists(path):
        return False
    entry = hostname if int(port) == 22 else f"[{hostname}]:{port}"
    with _lock:
        keys = paramiko.HostKeys(path)
        if entry not in keys:
            return False
        del keys[entry]
        keys.save(path)
    return True
