"""TLS certificate pinning for the Proxmox API (trust on first use).

Proxmox ships a self-signed certificate, so the API client historically used
verify=False — any machine on the path could impersonate Proxmox and capture
the API token. When CA verification is off we now pin the SHA-256
fingerprint of the certificate seen on first contact and refuse a different
one afterwards.

After a legitimate certificate change on Proxmox run:
    python manage.py forget_proxmox_hostkey <host> --port <api port>
"""

import hashlib
import json
import logging
import os
import socket
import ssl
import threading

from django.conf import settings
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def _store_path():
    base = os.path.dirname(getattr(settings, "SSH_KNOWN_HOSTS",
                                   "/opt/proxorchestrator/.ssh/known_hosts"))
    return os.path.join(base, "proxmox_api_fingerprints.json")


def _load():
    try:
        with open(_store_path()) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _save(data):
    path = _store_path()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _fetch_fingerprint(host, port, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    return hashlib.sha256(der).hexdigest()


def pinned_fingerprint(host, port):
    """Return the pinned fingerprint, pinning the current one on first use."""
    key = f"{host}:{int(port)}"
    with _lock:
        data = _load()
        if key in data:
            return data[key]
        fp = _fetch_fingerprint(host, port)
        data[key] = fp
        _save(data)
    logger.warning("Pinned Proxmox API certificate for %s: sha256 %s", key, fp)
    return fp


def forget(host, port):
    key = f"{host}:{int(port)}"
    with _lock:
        data = _load()
        if data.pop(key, None) is None:
            return False
        _save(data)
    return True


class FingerprintAdapter(HTTPAdapter):
    """requests adapter that accepts only a certificate with this SHA-256."""

    def __init__(self, fingerprint, **kwargs):
        self._fingerprint = fingerprint
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["assert_fingerprint"] = self._fingerprint
        return super().init_poolmanager(*args, **kwargs)
