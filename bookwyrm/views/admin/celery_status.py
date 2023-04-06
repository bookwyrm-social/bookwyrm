""" celery status """
import json

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET
from django import forms
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

        form = ClearCeleryForm()

        data = {
            "stats": stats,
            "active_tasks": active_tasks,
            "queues": queues,
            "form": form,
            "errors": errors,
        }
        return TemplateResponse(request, "settings/celery.html", data)

    def post(self, request):
        """Submit form to clear queues"""
        form = ClearCeleryForm(request.POST)
        if form.is_valid():
            if len(celery.control.ping()) != 0:
                return HttpResponse(
                    "Refusing to delete tasks while Celery worker is active"
                )
            pipeline = r.pipeline()
            for queue in form.cleaned_data["queues"]:
                for task in r.lrange(queue, 0, -1):
                    task_json = json.loads(task)
                    if task_json["headers"]["task"] in form.cleaned_data["tasks"]:
                        pipeline.lrem(queue, 0, task)
            results = pipeline.execute()

        return HttpResponse(f"Deleted {sum(results)} tasks")


class ClearCeleryForm(forms.Form):
    """Form to clear queues"""

    queues = forms.MultipleChoiceField(
        label="Queues",
        choices=[
            (LOW, "Low prioirty"),
            (MEDIUM, "Medium priority"),
            (HIGH, "High priority"),
            (IMPORTS, "Imports"),
            (BROADCAST, "Broadcasts"),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    tasks = forms.MultipleChoiceField(
        label="Tasks", choices=[], widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        celery.loader.import_default_modules()
        self.fields["tasks"].choices = sorted(
            [(k, k) for k in celery.tasks.keys() if not k.startswith("celery.")]
        )


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
