import django_filters

from netbox.filtersets import NetBoxModelFilterSet
from tenancy.models import Tenant

from .models import Drawing


class DrawingFilterSet(NetBoxModelFilterSet):
    tenant_id = django_filters.ModelMultipleChoiceFilter(field_name='tenant', queryset=Tenant.objects.all())
    tenant = django_filters.ModelMultipleChoiceFilter(
        field_name='tenant__slug', to_field_name='slug', queryset=Tenant.objects.all()
    )

    class Meta:
        model = Drawing
        fields = ('id', 'title', 'state')
