from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer

from ..models import Drawing


class DrawingSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_drawing_canvas-api:drawing-detail')

    class Meta:
        model = Drawing
        fields = ('id', 'url', 'display', 'title', 'tenant', 'state', 'revision', 'created', 'last_updated')
        brief_fields = ('id', 'url', 'display', 'title')
