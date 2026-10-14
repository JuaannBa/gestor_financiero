from rest_framework.routers import SimpleRouter

from .views import AccountViewSet

app_name = "accounts"

router = SimpleRouter()
router.register("accounts", AccountViewSet, basename="account")

urlpatterns = router.urls
