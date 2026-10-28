"""Private-network preview with dedicated database, cache and required credentials."""
import os

ALLOWED_HOSTS = os.environ.get('DRAWING_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
DATABASE = {
    'NAME': 'drawing_preview', 'USER': 'drawing_preview',
    'PASSWORD': os.environ['DRAWING_DB_PASSWORD'], 'HOST': 'db', 'PORT': 5432,
    'TEST': {'CHARSET': 'UTF8', 'TEMPLATE': 'template0'},
}
REDIS = {
    name: {'HOST': 'redis', 'PORT': 6379, 'DATABASE': index}
    for index, name in enumerate(('tasks', 'caching'))
}
SECRET_KEY = os.environ['DRAWING_SECRET_KEY']
API_TOKEN_PEPPERS = {1: os.environ['DRAWING_API_PEPPER']}
PLUGINS = ['netbox_drawing_canvas']
PLUGINS_CONFIG = {'netbox_drawing_canvas': {'synthetic_demo': True}}
LOGIN_REQUIRED = True
SESSION_COOKIE_NAME = 'drawing_preview_sessionid'
CSRF_COOKIE_NAME = 'drawing_preview_csrftoken'
DEFAULT_PERMISSIONS = {}
DEBUG = False
DEVELOPER = False
