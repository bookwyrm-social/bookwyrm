""" bookwyrm settings and configuration """
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
from bookwyrm.settings import *

CELERY_BROKER_URL = "redis://:{}@redis_broker:{}/0".format(
    requests.utils.quote(env("REDIS_BROKER_PASSWORD", "")), env("REDIS_BROKER_PORT")
)
CELERY_RESULT_BACKEND = "redis://:{}@redis_broker:{}/0".format(
    requests.utils.quote(env("REDIS_BROKER_PASSWORD", "")), env("REDIS_BROKER_PORT")
)

CELERY_TASK_ROUTES = ([
    # high - should really happen ASAP
    ("bookwyrm.emailing.*", {"queue": "high_priority"}),
    # medium - should really happen
    ("bookwyrm.activitypub.base_activity.*", {"queue": "medium_priority"}),
    ("bookwyrm.views.inbox.*", {"queue": "medium_priority"}),
    ("bookwyrm.broadcast.*", {"queue": "medium_priority"}),
    ("bookwyrm.activitystreams.*", {"queue": "medium_priority"}),
    # low - no rush
    ("bookwyrm.connectors.abstract_connector.*", {"queue": "low_priority"}),
    ("bookwyrm.goodreads_import.*", {"queue": "low_priority"}),
    ("bookwyrm.models.user.*", {"queue": "low_priority"}),
    ("bookwyrm.suggested_users.*", {"queue": "low_priority"}),
    ("bookwyrm.preview_images.*", {"queue": "low_priority"}),
])

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
FLOWER_PORT = env("FLOWER_PORT")

INSTALLED_APPS = INSTALLED_APPS + [
    "celerywyrm",
]

ROOT_URLCONF = "celerywyrm.urls"

WSGI_APPLICATION = "celerywyrm.wsgi.application"
