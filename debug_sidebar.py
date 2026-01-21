"""Debug script to check why sidebar doesn't show correct items"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.admin.sites import site
from django.test import RequestFactory
from django.apps import apps

u = User.objects.get(username='GV001')

# Giả lập request
rf = RequestFactory()
request = rf.get('/admin/')
request.user = u

# Check tất cả apps đã đăng ký trong admin
print('=== All Registered Admin Apps ===')
for app_label, app_models in site._registry.items():
    print(f"  {app_label._meta.app_label}.{app_label._meta.model_name}")

print('\n=== All Installed Apps ===')
for app_config in apps.get_app_configs():
    print(f"  {app_config.label}: {app_config.verbose_name}")

# Lấy available_apps như Django Admin làm
available_apps = site.get_app_list(request)
print('\n=== Available Apps for GV001 (from Django Admin) ===')
for app in available_apps:
    print(f"App: {app['app_label']} - {app.get('name', 'N/A')}")
    for model in app.get('models', []):
        print(f"  Model: {model.get('object_name', 'N/A')}")

# Check if user has any data_table permissions
print('\n=== User data_table permissions ===')
print(f"data_table.view_hideshowfilter: {u.has_perm('data_table.view_hideshowfilter')}")
print(f"data_table.view_modelfilter: {u.has_perm('data_table.view_modelfilter')}")
print(f"data_table.view_pageitems: {u.has_perm('data_table.view_pageitems')}")

print('\n=== Custom Links from settings ===')
from django.conf import settings
custom_links = settings.JAZZMIN_SETTINGS.get('custom_links', {})
for app_label, links in custom_links.items():
    print(f"\nApp: {app_label}")
    for link in links:
        perms = link.get('permissions', [])
        perm_results = [u.has_perm(p) for p in perms]
        all_pass = all(perm_results) if perm_results else True
        print(f"  {link['name']}: permissions={perms}")
        print(f"    User has all? {all_pass} (individual: {perm_results})")

print('\n=== Simulating Jazzmin make_menu ===')
from jazzmin.utils import make_menu, get_settings
options = get_settings()

for app_label, links in custom_links.items():
    print(f"\nApp: {app_label}")
    result = make_menu(u, links, options, allow_appmenus=False)
    print(f"  Visible items: {[r['name'] for r in result]}")
