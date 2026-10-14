from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, RecurrenceViewSet, TransactionViewSet

app_name = "ledger"

router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("transactions", TransactionViewSet, basename="transaction")
router.register("recurrences", RecurrenceViewSet, basename="recurrence")

urlpatterns = router.urls
