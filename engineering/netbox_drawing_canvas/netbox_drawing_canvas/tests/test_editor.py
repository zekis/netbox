import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from core.models import ObjectType
from dcim.models import Device, DeviceRole, DeviceType, Location, Manufacturer, Rack, Site
from netbox_drawing_canvas.models import Drawing
from netbox_drawing_canvas.services import RevisionConflict, save_scene, validate_scene
from tenancy.models import Tenant
from users.models import ObjectPermission, User


def grant(user, model, actions=('view',), constraints=None):
    permission = ObjectPermission.objects.create(
        name='Synthetic permission', actions=list(actions), constraints=constraints
    )
    permission.object_types.add(ObjectType.objects.get_for_model(model))
    permission.users.add(user)
    return permission


def appearance(item, kind='device'):
    return {'id': str(uuid4()), 'kind': kind, 'object_id': item.pk, 'x': 100, 'y': 50}


class EditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Synthetic A', slug='synthetic-a')
        cls.foreign = Tenant.objects.create(name='Synthetic B', slug='synthetic-b')
        cls.site = Site.objects.create(name='Synthetic Site', slug='synthetic-site', tenant=cls.tenant)
        cls.other_site = Site.objects.create(name='Other Site', slug='other-site', tenant=cls.foreign)
        cls.location = Location.objects.create(name='Synthetic Area', site=cls.site, tenant=cls.tenant)
        vendor = Manufacturer.objects.create(name='Synthetic Vendor', slug='synthetic-vendor')
        model = DeviceType.objects.create(manufacturer=vendor, model='Demo', slug='demo')
        role = DeviceRole.objects.create(name='Demo', slug='demo')
        cls.device = Device.objects.create(name='Visible switch', site=cls.site, tenant=cls.tenant,
                                           device_type=model, role=role)
        cls.hidden = Device.objects.create(name='Hidden switch', site=cls.site, tenant=cls.tenant,
                                           device_type=model, role=role)
        cls.other_device = Device.objects.create(name='Foreign switch', site=cls.site, tenant=cls.foreign,
                                                 device_type=model, role=role)
        cls.unassigned = Rack.objects.create(name='Unassigned rack', site=cls.site)
        cls.rack = Rack.objects.create(name='Synthetic rack', site=cls.site, tenant=cls.tenant)
        cls.drawing = Drawing.objects.create(title='Sheet A', tenant=cls.tenant, site=cls.site)
        cls.other_drawing = Drawing.objects.create(title='Sheet B', tenant=cls.foreign)
        cls.user = User.objects.create_user(username='synthetic-editor')
        grant(cls.user, Tenant, constraints={'pk': cls.tenant.pk})
        grant(cls.user, Site, constraints={'tenant_id': cls.tenant.pk})
        grant(cls.user, Location, constraints={'tenant_id': cls.tenant.pk})
        grant(cls.user, Device, constraints={'pk': cls.device.pk})
        grant(cls.user, Rack)
        grant(cls.user, Drawing, ('view', 'change', 'add'), {'tenant_id': cls.tenant.pk})

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('plugins:netbox_drawing_canvas:drawing_scene', args=[self.drawing.pk])
        self.scene = {'schema_version': 1, 'appearances': [appearance(self.device), appearance(self.rack, 'rack')]}

    def save(self, **changes):
        data = {'revision': 1, 'state': 'draft', 'scene': self.scene}
        data.update(changes)
        return self.client.post(self.url, data, content_type='application/json')

    def test_persistence_and_stale_save(self):
        response = self.save(state='review')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['revision'], 2)
        self.assertEqual(self.client.get(self.url).json()['scene'], self.scene)
        self.assertEqual(self.save().status_code, 409)
        self.drawing.refresh_from_db()
        self.assertEqual(self.drawing.state, 'review')
        self.assertEqual(self.drawing.scene, self.scene)

    def test_same_equipment_on_multiple_sheets(self):
        second = Drawing.objects.create(title='Second appearance', tenant=self.tenant)
        self.assertEqual(self.save().status_code, 200)
        save_scene(self.user, second.pk, 1, self.scene, 'draft')
        self.assertEqual(Device.objects.filter(pk=self.device.pk).count(), 1)
        second.refresh_from_db()
        self.assertEqual(second.scene, self.scene)

    def test_cross_tenant_hidden_null_and_invalid_references_rejected(self):
        for item, kind in ((self.other_device, 'device'), (self.hidden, 'device'), (self.unassigned, 'rack')):
            with self.subTest(item=item.name):
                self.scene['appearances'] = [appearance(item, kind)]
                self.assertEqual(self.save().status_code, 400)
        self.scene['appearances'][0]['object_id'] = 999999999
        self.assertEqual(self.save().status_code, 400)
        self.drawing.refresh_from_db()
        self.assertEqual(self.drawing.revision, 1)

    def test_foreign_sheet_and_equipment_not_disclosed(self):
        for endpoint in ('drawing', 'drawing_scene', 'drawing_equipment'):
            url = reverse(f'plugins:netbox_drawing_canvas:{endpoint}', args=[self.other_drawing.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
        url = reverse('plugins:netbox_drawing_canvas:drawing_equipment', args=[self.drawing.pk])
        results = self.client.get(url).json()['results']
        self.assertEqual([row['id'] for row in results], [self.device.pk])
        self.assertEqual(self.client.get(url, {'object_id': self.hidden.pk}).status_code, 404)
        self.assertEqual(self.client.get(url, {'object_id': 'invalid'}).status_code, 400)

    def test_tenant_permission_alone_does_not_grant_sheet_access(self):
        viewer = User.objects.create_user(username='tenant-only')
        grant(viewer, Tenant)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_sheet_permission_without_tenant_permission_denied(self):
        viewer = User.objects.create_user(username='sheet-only')
        grant(viewer, Drawing, ('view', 'change'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.save().status_code, 404)

    def test_viewer_cannot_save(self):
        viewer = User.objects.create_user(username='read-only')
        grant(viewer, Drawing)
        grant(viewer, Tenant)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.save().status_code, 403)
        response = self.client.get(self.drawing.get_absolute_url())
        self.assertContains(response, 'data-editable="false"')

    def test_sheet_constraints_within_the_same_tenant(self):
        other = Drawing.objects.create(title='Restricted sheet', tenant=self.tenant)
        viewer = User.objects.create_user(username='one-sheet-only')
        grant(viewer, Tenant)
        grant(viewer, Drawing, ('view', 'change'), {'pk': self.drawing.pk})
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        url = reverse('plugins:netbox_drawing_canvas:drawing_scene', args=[other.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {}, content_type='application/json').status_code, 404)

    def test_revoked_equipment_blocks_read_and_write(self):
        self.assertEqual(self.save().status_code, 200)
        Device.objects.filter(pk=self.device.pk).update(tenant=self.foreign)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.save(revision=2).status_code, 400)

    def test_scene_schema_validation(self):
        invalid = [None, [], {}, {'schema_version': 2, 'appearances': []}]
        for field, value in [('id', 'not-uuid'), ('kind', 'cable'), ('object_id', True),
                             ('x', float('nan')), ('y', 100001), ('x', '42')]:
            scene = copy.deepcopy(self.scene)
            scene['appearances'][0][field] = value
            invalid.append(scene)
        duplicate = copy.deepcopy(self.scene)
        duplicate['appearances'].append(duplicate['appearances'][0])
        invalid.append(duplicate)
        for scene in invalid:
            with self.subTest(scene=scene), self.assertRaises(ValidationError):
                validate_scene(scene, self.drawing, self.user)

    def test_malformed_request_and_revision(self):
        for body in ('[1]', '{', 'null'):
            self.assertEqual(self.client.post(self.url, body, content_type='application/json').status_code, 400)
        self.assertEqual(self.save(revision=True).status_code, 409)
        self.assertEqual(self.save(state='published').status_code, 400)

    def test_create_context_validation(self):
        url = reverse('plugins:netbox_drawing_canvas:drawing_list')
        response = self.client.post(url, {'title': 'New sheet', 'tenant': self.tenant.pk, 'site': self.site.pk,
                                          'location': self.location.pk})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Drawing.objects.filter(title='New sheet').exists())
        for tenant, site in ((self.tenant.pk, self.other_site.pk), ('', self.site.pk)):
            self.client.post(url, {'title': 'Invalid sheet', 'tenant': tenant, 'site': site})
            self.assertFalse(Drawing.objects.filter(title='Invalid sheet').exists())

    def test_add_constraints_checked_and_rolled_back(self):
        user = User.objects.create_user(username='constrained-creator')
        grant(user, Tenant)
        grant(user, Drawing, ('add',), {'tenant_id': self.tenant.pk})
        self.client.force_login(user)
        url = reverse('plugins:netbox_drawing_canvas:drawing_list')
        self.assertEqual(self.client.post(url, {'title': 'Denied', 'tenant': self.foreign.pk}).status_code, 403)
        self.assertFalse(Drawing.objects.filter(title='Denied').exists())

    def test_cross_tenant_site_model_validation(self):
        obj = Drawing(title='Invalid', tenant=self.tenant, site=self.other_site)
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_csrf_and_anonymous_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {}, content_type='application/json').status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_read_only_api_is_permission_filtered(self):
        url = reverse('plugins-api:netbox_drawing_canvas-api:drawing-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()
        rows = rows.get('results', rows) if isinstance(rows, dict) else rows
        self.assertEqual([row['id'] for row in rows], [self.drawing.pk])
        self.assertEqual(self.client.post(url, {}).status_code, 405)


class ConcurrentSaveTests(TransactionTestCase):
    def test_only_one_simultaneous_save_wins(self):
        tenant = Tenant.objects.create(name='Concurrency Lab', slug='concurrency-lab')
        drawing = Drawing.objects.create(title='Race', tenant=tenant)
        user = User.objects.create_superuser(username='synthetic-race-user')
        barrier = Barrier(2)

        def write(state):
            try:
                actor = User.objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                save_scene(actor, drawing.pk, 1, {'schema_version': 1, 'appearances': []}, state)
                return 'saved'
            except RevisionConflict:
                return 'conflict'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(write, ['draft', 'review']))
        self.assertCountEqual(outcomes, ['saved', 'conflict'])
        drawing.refresh_from_db()
        self.assertEqual(drawing.revision, 2)
