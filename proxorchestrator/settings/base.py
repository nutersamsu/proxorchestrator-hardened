import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env from the project root (or /opt/proxorchestrator/.env in production)
load_dotenv(BASE_DIR / ".env")
_prod_env = Path("/opt/proxorchestrator/.env")
if _prod_env.is_file() and os.access(_prod_env, os.R_OK):
    load_dotenv(_prod_env)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
_INSECURE_KEYS = {"", "insecure-default-change-me", "change-me-to-a-random-50-char-string"}
if SECRET_KEY in _INSECURE_KEYS or len(SECRET_KEY) < 40:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-never-use-in-production-0123456789"
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "SECRET_KEY must be set to a random value of at least 40 characters "
            "in /opt/proxorchestrator/.env"
        )

# Comma-separated host names / IPs this server answers to. A wildcard makes
# Host-header attacks possible, so it is only honoured when explicitly
# acknowledged with ALLOW_ANY_HOST=true.
_raw_hosts = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]
if "*" in ALLOWED_HOSTS and os.environ.get("ALLOW_ANY_HOST", "").lower() != "true":
    ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h != "*"] or ["localhost", "127.0.0.1"]

# Base URL used in links sent by email (password reset). Never derived from
# the request Host header. Example: https://proxorchestrator.example.lan:8443
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

SITE_ID = 1

# ---------------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # Daphne must be before staticfiles per Channels docs
    "daphne",
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    # django-allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.microsoft",
    # ProxOrchestrator apps
    "apps.core",
    "apps.wizard",
    "apps.proxmox",
    "apps.converter",
    "apps.importer",
    "apps.inventory",
    "apps.vmmanager",
    "apps.exporter",
    "apps.authconfig",
    "apps.emailconfig",
    "apps.certificates",
    "apps.vmcreator",
    "apps.lxc",
    # Django Channels (WebSocket support)
    "channels",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.core.security.AccessControlMiddleware",
    "apps.core.middleware.ForcePasswordChangeMiddleware",
    "apps.core.middleware.ForceMFASetupMiddleware",
    "apps.core.middleware.WizardRedirectMiddleware",
]

# ---------------------------------------------------------------------------
# URL / WSGI
# ---------------------------------------------------------------------------

ROOT_URLCONF = "proxorchestrator.urls"

WSGI_APPLICATION = "proxorchestrator.wsgi.application"
ASGI_APPLICATION = "proxorchestrator.asgi.application"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_db_path = os.environ.get("DB_PATH", "/opt/proxorchestrator/db.sqlite3")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _db_path,
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

UPLOAD_ROOT = os.environ.get("UPLOAD_ROOT", "/opt/proxorchestrator/uploads")
MEDIA_URL = "/media/"
MEDIA_ROOT = UPLOAD_ROOT

# Where Django writes large upload temp files before the view saves them.
# Defaults to the OS temp dir (/tmp on Linux, often a small tmpfs).
# Set UPLOAD_TEMP_DIR in .env to a path on a disk with enough free space
# when importing large images (e.g. a 15 GB qcow2 needs 15 GB here).
_upload_temp = os.environ.get("UPLOAD_TEMP_DIR", "")
if _upload_temp:
    FILE_UPLOAD_TEMP_DIR = _upload_temp

# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# ---------------------------------------------------------------------------
# Django Channels (WebSocket)
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")],
        },
    },
}

# ---------------------------------------------------------------------------
# Encrypted fields
# ---------------------------------------------------------------------------

FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")

# ---------------------------------------------------------------------------
# Authentication backends
# NOTE: LDAP and allauth backends are added dynamically by apps.authconfig
# ---------------------------------------------------------------------------

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# ---------------------------------------------------------------------------
# django-allauth
# ---------------------------------------------------------------------------

# Local accounts are created only by administrators. allauth is used solely
# for the Microsoft Entra ID flow; its local login/signup views are blocked
# by AccessControlMiddleware and closed by the adapter as well.
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]
ACCOUNT_ADAPTER = "apps.authconfig.adapters.ClosedAccountAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = True
# Require a POST (with CSRF token) to start the OAuth flow.
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_ADAPTER = "apps.authconfig.adapters.AutoSignupSocialAdapter"
ACCOUNT_SIGNUP_REDIRECT_URL = "/"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"

# ---------------------------------------------------------------------------
# Logging — errors to gunicorn error log
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": "/var/log/proxorchestrator/django.log",
        },
    },
    "root": {
        "handlers": ["file"],
        "level": "WARNING",
    },
    "loggers": {
        "django.request": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Help system
# ---------------------------------------------------------------------------

HELP_DIR = BASE_DIR / "help"

# ---------------------------------------------------------------------------
# CSRF / Security
# ---------------------------------------------------------------------------

# Tell Django it is behind an SSL-terminating reverse proxy (nginx).
# Nginx sets X-Forwarded-Proto: https; without this, Django sees the gunicorn
# connection as plain HTTP and its CSRF referer check fails.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The app is only served over HTTPS (nginx on WEB_PORT).
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", 8 * 3600))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 0))

# Origins allowed to POST (needed behind a reverse proxy on another host/port).
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
if PUBLIC_BASE_URL and PUBLIC_BASE_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(PUBLIC_BASE_URL)

# Shared cache (login throttling must be shared by all gunicorn workers).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("CACHE_URL", "redis://127.0.0.1:6379/2"),
        "KEY_PREFIX": "proxorchestrator",
    }
}

LOGIN_MAX_FAILURES_PER_USER = int(os.environ.get("LOGIN_MAX_FAILURES_PER_USER", 5))
LOGIN_MAX_FAILURES_PER_IP = int(os.environ.get("LOGIN_MAX_FAILURES_PER_IP", 20))
LOGIN_LOCKOUT_SECONDS = int(os.environ.get("LOGIN_LOCKOUT_SECONDS", 900))

# Proxmox SSH host keys pinned on first use (see apps/proxmox/hostkeys.py).
SSH_KNOWN_HOSTS = os.environ.get(
    "SSH_KNOWN_HOSTS", "/opt/proxorchestrator/.ssh/known_hosts"
)

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

WEB_PORT = int(os.environ.get("WEB_PORT", "8443"))

# ---------------------------------------------------------------------------
# Email
# Defaults — overridden at startup by apps.emailconfig.apps.EmailConfigApp
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@proxorchestrator.local"
