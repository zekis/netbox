import math
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from dcim.models import Device, Location, Rack, Site
from tenancy.models import Tenant

from .models import Drawing

EQUIPMENT = {'device': Device, 'rack': Rack}


def drawings_for(user, action='view'):
    return Drawing.objects.restrict(user, action).filter(tenant__in=Tenant.objects.restrict(user, 'view'))


def validate_context(drawing, user):
    for model, pk in ((Tenant, drawing.tenant_id), (Site, drawing.site_id), (Location, drawing.location_id)):
        if pk is not None and not model.objects.restrict(user, 'view').filter(pk=pk).exists():
            raise ValidationError('A referenced tenant, site or location is unavailable.')
    drawing.full_clean()


def equipment_for(user, drawing, kind):
    return EQUIPMENT[kind].objects.restrict(user, 'view').filter(tenant_id=drawing.tenant_id)


def validate_scene(scene, drawing, user):
    if not isinstance(scene, dict) or set(scene) != {'schema_version', 'appearances'}:
        raise ValidationError('Scene must contain schema_version and appearances only.')
    if type(scene['schema_version']) is not int or scene['schema_version'] != 1:
        raise ValidationError('Unsupported scene schema version.')
    appearances = scene['appearances']
    if not isinstance(appearances, list) or len(appearances) > 500:
        raise ValidationError('A sheet supports at most 500 appearances.')
    seen, refs = set(), {kind: set() for kind in EQUIPMENT}
    for item in appearances:
        if not isinstance(item, dict) or set(item) != {'id', 'kind', 'object_id', 'x', 'y'}:
            raise ValidationError('Invalid appearance fields.')
        try:
            identifier = str(UUID(item['id']))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError('Appearance ID must be a UUID.') from None
        if identifier != item['id'] or identifier in seen:
            raise ValidationError('Appearance IDs must be canonical and unique within the sheet.')
        seen.add(identifier)
        if not isinstance(item['kind'], str) or item['kind'] not in EQUIPMENT:
            raise ValidationError('Only device and rack appearances are supported.')
        if type(item['object_id']) is not int or item['object_id'] <= 0:
            raise ValidationError('Object ID must be a positive integer.')
        for axis in ('x', 'y'):
            value = item[axis]
            if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 100000:
                raise ValidationError('Coordinates must be finite and between -100000 and 100000.')
        refs[item['kind']].add(item['object_id'])
    for kind, ids in refs.items():
        allowed = set(equipment_for(user, drawing, kind).filter(pk__in=ids).values_list('pk', flat=True))
        if ids != allowed:
            raise ValidationError('Equipment is unavailable, unassigned, or belongs to another tenant.')


class RevisionConflict(Exception):
    pass


@transaction.atomic
def save_scene(user, pk, revision, scene, state):
    # Serializes writes on the sheet; a second editor observes the committed revision.
    drawing = drawings_for(user, 'change').select_for_update().filter(pk=pk).first()
    if drawing is None or not drawings_for(user).filter(pk=pk).exists():
        raise PermissionDenied
    if type(revision) is not int or revision != drawing.revision:
        raise RevisionConflict
    if state not in ('draft', 'review'):
        raise ValidationError('Invalid drawing state.')
    validate_context(drawing, user)
    validate_scene(scene, drawing, user)
    drawing.snapshot()
    drawing.scene, drawing.state = scene, state
    drawing.revision += 1
    drawing.save()
    return drawing
