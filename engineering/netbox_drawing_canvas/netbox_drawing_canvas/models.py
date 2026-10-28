from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from netbox.models import NetBoxModel


def empty_scene():
    return {'schema_version': 1, 'appearances': []}


class Drawing(NetBoxModel):
    """One sheet; appearances never own or duplicate equipment records."""

    title = models.CharField(max_length=200)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.PROTECT)
    site = models.ForeignKey('dcim.Site', on_delete=models.PROTECT, blank=True, null=True)
    location = models.ForeignKey('dcim.Location', on_delete=models.PROTECT, blank=True, null=True)
    state = models.CharField(max_length=16, choices=(('draft', 'Draft'), ('review', 'Review')), default='draft')
    revision = models.PositiveIntegerField(default=1, editable=False)
    scene = models.JSONField(default=empty_scene)
    source_reference = models.CharField(
        max_length=500, blank=True, help_text='Portable reference only; no file upload.'
    )

    class Meta:
        ordering = ('title', 'pk')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('plugins:netbox_drawing_canvas:drawing', args=[self.pk])

    def clean(self):
        super().clean()
        if self.site_id and self.site.tenant_id != self.tenant_id:
            raise ValidationError({'site': 'Site must belong to the drawing tenant.'})
        if self.location_id:
            if self.location.tenant_id != self.tenant_id:
                raise ValidationError({'location': 'Location must belong to the drawing tenant.'})
            if self.site_id != self.location.site_id:
                raise ValidationError({'location': 'Location must belong to the selected site.'})
