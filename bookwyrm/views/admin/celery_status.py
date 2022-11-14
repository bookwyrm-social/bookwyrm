""" celery status """
from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
import redis

from celerywyrm import settings
from bookwyrm.tasks import app as celery

r = redis.Redis(
    host=settings.REDIS_BROKER_HOST,
    port=settings.REDIS_BROKER_PORT,
    password=settings.REDIS_BROKER_PASSWORD,
    db=settings.REDIS_BROKER_DB_INDEX,
)

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class CeleryStatus(View):
    """Are your tasks running? Well you'd better go catch them"""

    def get(self, request):
        """See workers and active tasks"""
        errors = []
        try:
            inspect = celery.control.inspect()
            stats = inspect.stats()
            active_tasks = inspect.active()
        # pylint: disable=broad-except
        except Exception as err:
            stats = active_tasks = None
            errors.append(err)

        try:
            queues = {
                "low_priority": r.llen("low_priority"),
                "medium_priority": r.llen("medium_priority"),
                "high_priority": r.llen("high_priority"),
            }
        # pylint: disable=broad-except
        except Exception as err:
            queues = None
            errors.append(err)

        data = {
            "stats": stats,
            "active_tasks": active_tasks,
            "queues": queues,
            "errors": errors,
        }
        return TemplateResponse(request, "settings/celery.html", data)
