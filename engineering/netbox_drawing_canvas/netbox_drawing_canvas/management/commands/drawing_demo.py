from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Rack, Site
from netbox_drawing_canvas.models import Drawing
from tenancy.models import Tenant


class Command(BaseCommand):
    help = 'Create synthetic example equipment and one drawing in an explicitly opted-in development instance.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.PLUGINS_CONFIG['netbox_drawing_canvas'].get('synthetic_demo', False):
            raise CommandError('Requires synthetic_demo=True in plugin configuration. Use an isolated database only.')
        tenant, _ = Tenant.objects.get_or_create(name='Synthetic Lab', slug='synthetic-lab')
        site, _ = Site.objects.get_or_create(name='Synthetic Site', slug='synthetic-site', defaults={'tenant': tenant})
        manufacturer, _ = Manufacturer.objects.get_or_create(name='Synthetic Vendor', slug='synthetic-vendor')
        model, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer, model='Demo Switch', slug='demo-switch', defaults={'u_height': 1}
        )
        role, _ = DeviceRole.objects.get_or_create(name='Synthetic Switch', slug='synthetic-switch', color='2196f3')
        rack, _ = Rack.objects.get_or_create(name='Demo Rack', site=site, defaults={'tenant': tenant})
        switches = [Device.objects.get_or_create(
            name=f'Demo Switch {number}', site=site,
            defaults={'tenant': tenant, 'role': role, 'device_type': model},
        )[0] for number in (1, 2)]
        # No rack position, ports, modules, quantities or physical cables are fabricated.
        drawing, created = Drawing.objects.get_or_create(
            title='Synthetic lab · equipment overview', tenant=tenant, defaults={'site': site}
        )
        if created:
            drawing.scene = {'schema_version': 1, 'appearances': [
                {'id': str(uuid4()), 'kind': kind, 'object_id': item.pk, 'x': x, 'y': y}
                for kind, item, x, y in (
                    ('rack', rack, 40, 140), ('device', switches[0], 290, 60), ('device', switches[1], 290, 240)
                )
            ]}
            drawing.save()
        self.stdout.write(drawing.get_absolute_url())
