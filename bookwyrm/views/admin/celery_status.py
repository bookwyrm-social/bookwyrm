""" celery status """
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET
import redis

from celerywyrm import settings
from bookwyrm.tasks import app as celery, LOW, MEDIUM, HIGH, IMPORTS, BROADCAST

r = redis.from_url(settings.REDIS_BROKER_URL)

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
                LOW: r.llen(LOW),
                MEDIUM: r.llen(MEDIUM),
                HIGH: r.llen(HIGH),
                IMPORTS: r.llen(IMPORTS),
                BROADCAST: r.llen(BROADCAST),
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


@require_GET
# pylint: disable=unused-argument
def celery_ping(request):
    """Just tells you if Celery is on or not"""
    try:
        ping = celery.control.inspect().ping()
        if ping:
            return HttpResponse()
    # pylint: disable=broad-except
    except Exception:
        pass

    return HttpResponse(status=500)
