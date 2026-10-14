from rest_framework.routers import SimpleRouter

from .views import BudgetViewSet

app_name = "budgets"

router = SimpleRouter()
router.register("budgets", BudgetViewSet, basename="budget")

urlpatterns = router.urls
