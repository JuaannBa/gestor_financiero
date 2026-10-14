"""Production settings — gunicorn behind nginx on the home network."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY, env

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured("Set a real SECRET_KEY in .env for production")

# No TLS on the LAN: SSL redirect off, but harden everything else
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# gunicorn access/error logs go to docker stdout (picked up by the console handler)
