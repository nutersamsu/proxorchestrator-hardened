import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "proxorchestrator.settings.production")

django_asgi_app = get_asgi_application()

from apps.lxc.routing import websocket_urlpatterns as lxc_ws_patterns  # noqa: E402
from apps.vmcreator.routing import websocket_urlpatterns as vm_ws_patterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Reject cross-site WebSocket handshakes: these sockets drive a root
        # shell on the Proxmox host, so a foreign page must never open one
        # with the admin's session cookie.
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(lxc_ws_patterns + vm_ws_patterns))
        ),
    }
)
