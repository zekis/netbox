from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from ..filtersets import DrawingFilterSet
from ..services import drawings_for
from .serializers import DrawingSerializer


class DrawingViewSet(ReadOnlyModelViewSet):
    """Discovery only. All scene mutations use the revision-checked editor endpoint."""

    permission_classes = (IsAuthenticated,)
    serializer_class = DrawingSerializer
    filterset_class = DrawingFilterSet

    def get_queryset(self):
        return drawings_for(self.request.user)
