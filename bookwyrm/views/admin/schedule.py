""" Scheduled celery tasks """
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django_celery_beat.models import PeriodicTask, IntervalSchedule


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
# pylint: disable=no-self-use
class ScheduledTasks(View):
    """Manage automated flagging"""

    def get(self, request):
        """view schedules"""
        data = {}
        data["tasks"] = PeriodicTask.objects.all()
        data["schedules"] = IntervalSchedule.objects.all()
        return TemplateResponse(request, "settings/schedules.html", data)

    # pylint: disable=unused-argument
    def post(self, request, task_id):
        """un-schedule a task"""
        task = PeriodicTask.objects.get(id=task_id)
        task.delete()
        return redirect("settings-schedules")
