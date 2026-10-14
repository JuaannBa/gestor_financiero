from rest_framework.routers import SimpleRouter

from .views import ImportBatchViewSet

app_name = "imports"

router = SimpleRouter()
router.register("imports", ImportBatchViewSet, basename="import")

urlpatterns = router.urls
