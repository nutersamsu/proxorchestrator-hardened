"""Thin wrapper around the root-owned proxorchestrator-nginx-helper.

The service account may only run that helper through sudo; it never writes
nginx configuration itself. See deploy/proxorchestrator-nginx-helper.
"""

import logging
import subprocess

logger = logging.getLogger(__name__)

HELPER = "/usr/local/sbin/proxorchestrator-nginx-helper"


class NginxHelperError(RuntimeError):
    pass


def _run(*args, stdin=None):
    result = subprocess.run(
        ["sudo", "-n", HELPER, *args],
        input=stdin, capture_output=True, text=True, shell=False, timeout=60,
    )
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()
        logger.error("nginx helper %s failed: %s", args[0], msg)
        raise NginxHelperError(msg or f"nginx helper {args[0]} failed")
    return result


def test():
    try:
        _run("test")
        return True
    except NginxHelperError:
        return False


def reload():
    _run("reload")


def set_port(port):
    _run("set-port", str(int(port)))


def write_ws(host, port, token_id, token_secret):
    _run("write-ws", str(host), str(int(port)), stdin=f"{token_id}\n{token_secret}\n")


def clear_ws():
    _run("clear-ws")


def acme_on():
    _run("acme-on")


def acme_off():
    _run("acme-off")
