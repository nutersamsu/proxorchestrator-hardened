"""Skip tests that need the Redis channel layer when no Redis is running.

On an installed system Redis is always there (install.sh sets it up); this only
matters when the test suite is run on a development machine or in CI.
"""

import socket
import unittest
from urllib.parse import urlparse

from django.conf import settings


def _redis_address():
    try:
        address = settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"][0]
        url = address["address"] if isinstance(address, dict) else address
    except (KeyError, IndexError, TypeError):
        url = "redis://127.0.0.1:6379/0"
    if isinstance(url, (list, tuple)):
        return url[0], int(url[1])
    parsed = urlparse(url)
    return parsed.hostname or "127.0.0.1", parsed.port or 6379


def redis_available():
    host, port = _redis_address()
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


requires_redis = unittest.skipUnless(
    redis_available(), "Redis is not running (needed for the channel layer)"
)
