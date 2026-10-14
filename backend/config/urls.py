from django.contrib import admin
from django.urls import include, path
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
    path("api/v1/auth/", include("apps.users.urls", namespace="auth")),
    path("api/v1/", include("apps.accounts.urls", namespace="accounts")),
    path("api/v1/", include("apps.ledger.urls", namespace="ledger")),
    path("api/v1/", include("apps.budgets.urls", namespace="budgets")),
    path("api/v1/reports/", include("apps.reports.urls", namespace="reports")),
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
