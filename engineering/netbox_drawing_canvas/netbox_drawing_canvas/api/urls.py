from rest_framework.routers import DefaultRouter

from .views import DrawingViewSet

router = DefaultRouter()
router.register('drawings', DrawingViewSet, basename='drawing')
urlpatterns = router.urls
