"""
ASGI config for digidine project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from channels.routing import get_default_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digidine.settings')
from digidine.routing import application
