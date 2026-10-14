from django.contrib import admin
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny

from config.health import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path(
        "api/v1/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="api-schema",
    ),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema", permission_classes=[AllowAny]),
        name="api-swagger",
    ),
    path(
        "api/v1/redoc/",
        SpectacularRedocView.as_view(url_name="api-schema", permission_classes=[AllowAny]),
        name="api-redoc",
    ),
]
