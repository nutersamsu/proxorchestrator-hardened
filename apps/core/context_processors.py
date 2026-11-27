"""Template context shared by every page."""

import hashlib
from functools import lru_cache
from pathlib import Path

from django.conf import settings


@lru_cache(maxsize=None)
def _css_version():
    """Short content hash of the app stylesheet.

    nginx serves /static/ with a 30-day "immutable" Cache-Control, so the URL
    must change whenever the file changes or browsers keep the old CSS.
    Computed once per process; update.sh restarts the services.
    """
    candidates = [
        Path(settings.STATIC_ROOT) / "css" / "proxorchestrator.css",
        *(Path(d) / "css" / "proxorchestrator.css" for d in settings.STATICFILES_DIRS),
    ]
    for path in candidates:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        except OSError:
            continue
    return "0"


def asset_versions(request):
    return {"css_version": _css_version()}
