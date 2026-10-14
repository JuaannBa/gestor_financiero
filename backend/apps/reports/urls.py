from django.urls import path

from .views import BalancesView, DashboardView

app_name = "reports"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("balances/", BalancesView.as_view(), name="balances"),
]
