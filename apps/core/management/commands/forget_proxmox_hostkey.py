from django.core.management.base import BaseCommand

from apps.proxmox import hostkeys
from apps.proxmox import tlspin


class Command(BaseCommand):
    help = ("Forget the pinned SSH host key and/or API certificate of a Proxmox host "
            "(after a legitimate reinstall or certificate renewal).")

    def add_arguments(self, parser):
        parser.add_argument("host")
        parser.add_argument("--port", type=int, default=22)

    def handle(self, host, port, **options):
        forgot_ssh = hostkeys.forget(host, port)
        forgot_tls = tlspin.forget(host, port)
        if forgot_ssh or forgot_tls:
            what = " and ".join(w for w, ok in (("SSH host key", forgot_ssh),
                                               ("API certificate", forgot_tls)) if ok)
            self.stdout.write(self.style.SUCCESS(
                f"Forgot {what} for {host}:{port}; it will be re-pinned on the next connection."))
        else:
            self.stdout.write(f"Nothing pinned for {host}:{port}.")
