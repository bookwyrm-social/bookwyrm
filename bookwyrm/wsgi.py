"""
WSGI config for bookwyrm project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/howto/deployment/wsgi/
"""

import os
from environs import Env
from django.core.wsgi import get_wsgi_application

Env.read_env()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookwyrm.settings")

application = get_wsgi_application()
