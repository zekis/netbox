# Validation — 2026-10-28

All data was synthetic. No production instance, credentials, database, or files were
accessed. The fork base was `engineering` at `ba70e33cf` (NetBox 4.7.4). A separate
upstream v4.2.9 source archive was used for the production-version compatibility
check; this did not access the user's production installation.

| Check | NetBox 4.2.9 / Django 5.1.8 | NetBox 4.7.4 / Django 6.1.2 |
| --- | --- | --- |
| Apply core + plugin migrations to isolated database | Passed | Passed |
| Plugin Django tests | 17 passed | 17 passed |
| Real Chromium canvas smoke test | Passed | Passed |
| `makemigrations netbox_drawing_canvas --check --dry-run` | No changes | No changes |
| Synthetic screenshot | [4.2.9](docs/canvas-netbox-4.2.9.png) | [4.7.4](docs/canvas-netbox-4.7.4.png) |

Additional checks: Ruff; JavaScript syntax via `node --check`; shell syntax; wheel
build; wheel contents (migration, templates, JS/CSS); local service launcher.
Python 3.12.16 and PostgreSQL 15.19 were used. NetBox requirements were installed in
two separate virtualenvs, substituting the binary psycopg extra at the pinned version.

Backend coverage includes scene persistence; stale revisions; a genuine simultaneous
save using two PostgreSQL connections (exactly one winner); the same equipment on
multiple sheets; cross-tenant, null-tenant, hidden and invalid references; tenant
permissions without sheet permissions and vice versa; same-tenant sheet constraints;
view-only access; revoked equipment access; schema/UUID/coordinate validation;
creation constraint rollback; site/location validation; CSRF; anonymous access; and
the filtered read-only discovery API.

The browser test uses actual NetBox pages and endpoints: selection/detail link,
dragging, dirty indicator, navigation cancellation, explicit save/reload, pointer
zoom, panning, appearance placement/removal, state persistence, and a visible 409
conflict between two browser tabs. The property panel opens NetBox's real equipment
detail view rather than duplicating module/port permission logic.

Development warnings: 4.7.4 reports missing built documentation static assets
(`staticfiles.W004`) and a deprecation warning for `LOGIN_REQUIRED`. The former is
an unbuilt core docs directory; the latter is retained for 4.2.9. Neither prevented
plugin tests or browser operation. Full NetBox core regression tests were not run.
Intermediate NetBox versions, real production deployment, and physical connection
authoring are not validated by this slice.

Local URLs during this task (loopback in the development runtime):

- 4.2.9: http://127.0.0.1:8009/plugins/drawing-canvas/
- 4.7.4: http://127.0.0.1:8010/plugins/drawing-canvas/

Authenticate with a local user created using `dev/manage.sh createsuperuser`; the
browser smoke user's session is temporary and is logged out at the end. See the
README for repeatable launcher and test commands. These URLs are not public hosting
and require access/port forwarding to the development runtime.
