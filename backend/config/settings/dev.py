"""Development settings — runserver and local tooling."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True

# Vite dev server
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)
CORS_ALLOW_CREDENTIALS = True
