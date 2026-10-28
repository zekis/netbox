"""Run through dev/manage.sh shell < dev/smoke.py with Playwright installed.

Authenticates a passwordless synthetic user via an in-memory test session. No tokens or
session artifacts are written to disk. Requires the synthetic development configuration.
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import Client
from playwright.sync_api import expect, sync_playwright

from netbox_drawing_canvas.models import Drawing
from users.models import User

assert settings.PLUGINS_CONFIG['netbox_drawing_canvas']['synthetic_demo']
expect.set_options(timeout=30000)
base = os.environ.get('DRAWING_DEV_URL', 'http://127.0.0.1:8009')
assert base.startswith('http://127.0.0.1:')
call_command('drawing_demo')
user, _ = User.objects.get_or_create(
    username='synthetic-browser', defaults={'is_superuser': True}
)
client = Client()
client.force_login(user)
sheet = Drawing.objects.get(title='Synthetic lab · equipment overview')
url = base + sheet.get_absolute_url()
screenshot = Path(os.environ.get('DRAWING_SCREENSHOT', '/tmp/drawing-canvas-smoke.png'))
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={'width': 1600, 'height': 1000})
    # Exercise ordinary HTTP hosting, where the secure-context randomUUID API is absent.
    context.add_init_script("Object.defineProperty(crypto, 'randomUUID', {value: undefined});")
    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                         'value': client.cookies[settings.SESSION_COOKIE_NAME].value,
                         'url': base}])
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(url)
    expect(page.locator('#save-status')).to_contain_text('Saved')
    original_count = page.locator('.appearance').count()
    assert original_count >= 3
    page.locator('.appearance.device').first.click()
    expect(page.locator('#properties')).to_contain_text('Open NetBox equipment details')
    assert '/dcim/devices/' in page.locator('#properties a').get_attribute('href')

    # Drag a real saved appearance and assert coordinates survive explicit Save/reopen.
    node = page.locator('.appearance.device').first
    identifier = node.get_attribute('data-id')
    old_left = node.evaluate('(el) => parseFloat(el.style.left)')
    box = node.bounding_box()
    page.mouse.move(box['x'] + 20, box['y'] + 20)
    page.mouse.down()
    page.mouse.move(box['x'] + 110, box['y'] + 80, steps=8)
    page.mouse.up()
    expect(page.locator('#save-status')).to_have_text('Unsaved changes')
    new_left = node.evaluate('(el) => parseFloat(el.style.left)')
    assert new_left == old_left + 90

    # Explicit navigation guard must preserve unsaved edits when dismissed.
    def dismiss(dialog):
        dialog.dismiss()
    page.on('dialog', dismiss)
    page.get_by_role('link', name='← Sheets').click()
    assert page.url == url
    page.remove_listener('dialog', dismiss)

    page.locator('#save-scene').click()
    expect(page.locator('#save-status')).to_contain_text('Saved')
    page.reload()
    expect(page.locator('#save-status')).to_contain_text('Saved')
    assert page.locator(f'[data-id="{identifier}"]').evaluate('(el) => parseFloat(el.style.left)') == new_left

    # Zoom at a specific pointer and pan on empty canvas; view changes do not dirty the sheet.
    canvas = page.locator('#canvas').bounding_box()
    x, y = canvas['x'] + canvas['width'] - 40, canvas['y'] + canvas['height'] - 40
    page.mouse.move(x, y)
    before = page.locator('#canvas-world').evaluate('(el) => getComputedStyle(el).transform')
    page.mouse.wheel(0, -200)
    page.wait_for_timeout(100)
    after = page.locator('#canvas-world').evaluate('(el) => getComputedStyle(el).transform')
    assert before != after
    page.mouse.down()
    page.mouse.move(x - 40, y - 30, steps=4)
    page.mouse.up()
    assert page.locator('#canvas-world').evaluate('(el) => getComputedStyle(el).transform') != after
    expect(page.locator('#save-status')).to_contain_text('Saved')
    page.locator('#reset-view').click()

    # Place another appearance of existing equipment, save, and reopen.
    page.locator('#equipment-list button').first.click()
    expect(page.locator('.appearance')).to_have_count(original_count + 1)
    page.locator('#save-scene').click()
    expect(page.locator('#save-status')).to_contain_text('Saved')
    page.reload()
    expect(page.locator('.appearance')).to_have_count(original_count + 1)

    # Two actual browser editors: the stale save must be visibly rejected and remain dirty.
    other = context.new_page()
    other.goto(url)
    expect(other.locator('#save-status')).to_contain_text('Saved')
    page.locator('#drawing-state').select_option('review')
    page.locator('#save-scene').click()
    expect(page.locator('#save-status')).to_contain_text('Saved')
    page.reload()
    expect(page.locator('#save-status')).to_contain_text('Saved')
    expect(page.locator('#drawing-state')).to_have_value('review')
    other.locator('#drawing-state').select_option('draft')
    other.locator('#save-scene').click()
    expect(other.locator('#drawing-error')).to_contain_text('Another editor saved')
    expect(other.locator('#save-status')).to_have_text('Unsaved changes')
    other.close()

    # Remove the temporary appearance to leave a useful three-item demonstration.
    page.locator('.appearance').last.click()
    page.get_by_role('button', name='Remove appearance').click()
    page.locator('#save-scene').click()
    expect(page.locator('#save-status')).to_contain_text('Saved')
    page.locator('.appearance.device').first.click()
    expect(page.locator('#properties a')).to_be_visible()
    page.screenshot(path=str(screenshot), full_page=True)
    assert not errors, errors
    browser.close()
client.logout()
print(f'Canvas smoke passed: drag, persistence, placement, details, pan/zoom, navigation guard, conflict. {screenshot}')
