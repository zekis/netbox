"""Isolated, loopback-only synthetic development configuration. Never use in production."""
import getpass
import os
import sys

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
DATABASE = {
    'NAME': os.environ.get('DRAWING_DEV_DB', 'drawing_canvas'),
    'USER': os.environ.get('DRAWING_DEV_DB_USER', getpass.getuser()),
    'PASSWORD': os.environ.get('DRAWING_DEV_DB_PASSWORD', ''),
    'HOST': '127.0.0.1', 'PORT': 55439,
    'TEST': {'CHARSET': 'UTF8', 'TEMPLATE': 'template0'},
}
REDIS = {
    name: {'HOST': '127.0.0.1', 'PORT': 56389, 'DATABASE': index}
    for index, name in enumerate(('tasks', 'caching'))
}
SECRET_KEY = 'synthetic-local-only-drawing-canvas-development-key-not-for-production'
PLUGINS = ['netbox_drawing_canvas']
PLUGINS_CONFIG = {'netbox_drawing_canvas': {'synthetic_demo': True}}
DEBUG = 'test' not in sys.argv
DEVELOPER = True
LOGIN_REQUIRED = True
DEFAULT_PERMISSIONS = {}
API_TOKEN_PEPPERS = {1: 'synthetic-local-only-drawing-canvas-api-pepper-not-for-production'}
# Keep the debug toolbar from covering the canvas/property controls.
INTERNAL_IPS = ['192.0.2.1']  # Documentation-only address; no loopback toolbar.
