import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "proxorchestrator.settings.production")

app = Celery("proxorchestrator")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "check-cert-expiry": {
        "task": "certificates.check_cert_expiry",
        "schedule": crontab(hour="*/6", minute=30),  # Every 6 hours: 00:30, 06:30, 12:30, 18:30
    },
    # Remove export packages nobody downloaded (EXPORT_RETENTION_HOURS, default 24 h).
    # These tasks existed upstream but were never scheduled, so packages piled up.
    "cleanup-old-exports": {
        "task": "exporter.cleanup_old_exports",
        "schedule": crontab(minute=15),
    },
    "cleanup-old-lxc-exports": {
        "task": "exporter.cleanup_old_lxc_exports",
        "schedule": crontab(minute=20),
    },
}
