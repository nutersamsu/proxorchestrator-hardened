"""Update the nginx WebSocket proxy config for VM/LXC console access.

The config is generated and validated by the root-owned
proxorchestrator-nginx-helper (see deploy/), which also adds an
auth_request check so the injected Proxmox API token can only be used for
console handshakes the logged-in user just opened.

Called automatically by a post_save signal on ProxmoxConfig,
or manually: python manage.py update_nginx_ws
"""

import logging

from django.core.management.base import BaseCommand

from apps.core import nginx_helper

logger = logging.getLogger(__name__)


def write_ws_conf(host, port, token_id="", token_secret=""):
    if not (host and token_id and token_secret):
        nginx_helper.clear_ws()
        return
    nginx_helper.write_ws(host, port, token_id, token_secret)
    logger.info("update_nginx_ws: console proxy updated (host=%s port=%s)", host, port)


def reload_nginx():
    try:
        nginx_helper.reload()
    except nginx_helper.NginxHelperError as exc:
        logger.error("nginx reload failed: %s", exc)
        return False
    logger.info("nginx reloaded successfully")
    return True


class Command(BaseCommand):
    help = "Update nginx WebSocket proxy config for VM console and reload nginx"

    def handle(self, *args, **options):
        from apps.wizard.models import ProxmoxConfig
        config = ProxmoxConfig.objects.first()
        if not config or not config.host:
            self.stderr.write("No ProxmoxConfig found or host not set — skipping")
            return

        write_ws_conf(config.host, config.api_port, config.api_token_id, config.api_token_secret)
        if reload_nginx():
            self.stdout.write(self.style.SUCCESS(
                f"nginx WebSocket proxy updated: /vm-ws/ → {config.host}:{config.api_port}"
            ))
        else:
            self.stderr.write("nginx reload failed — check nginx logs")
