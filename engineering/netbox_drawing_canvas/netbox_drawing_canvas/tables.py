import django_tables2 as tables

from netbox.tables import NetBoxTable

from .models import Drawing


class DrawingTable(NetBoxTable):
    title = tables.Column(linkify=True)

    class Meta(NetBoxTable.Meta):
        model = Drawing
        fields = ('title', 'state', 'revision')
