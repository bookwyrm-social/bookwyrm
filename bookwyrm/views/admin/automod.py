""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django_celery_beat.models import PeriodicTask

from bookwyrm import forms, models


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
@method_decorator(
    permission_required("bookwyrm.moderate_post", raise_exception=True),
    name="dispatch",
)
# pylint: disable=no-self-use
class AutoMod(View):
    """Manage automated flagging"""

    def get(self, request):
        """view rules"""
        return TemplateResponse(
            request, "settings/automod/rules.html", automod_view_data()
        )

    def post(self, request):
        """add rule"""
        form = forms.AutoModRuleForm(request.POST)
        if form.is_valid():
            form.save()
            form = forms.AutoModRuleForm()

        data = automod_view_data()
        data["form"] = form
        return TemplateResponse(request, "settings/automod/rules.html", data)


@require_POST
@permission_required("bookwyrm.moderate_user", raise_exception=True)
@permission_required("bookwyrm.moderate_post", raise_exception=True)
def schedule_automod_task(request):
    """scheduler"""
    form = forms.IntervalScheduleForm(request.POST)
    if not form.is_valid():
        data = automod_view_data()
        data["task_form"] = form
        return TemplateResponse(request, "settings/automod/rules.html", data)

    with transaction.atomic():
        schedule = form.save()
        PeriodicTask.objects.get_or_create(
            interval=schedule,
            name="automod-task",
            task="bookwyrm.models.antispam.automod_task",
        )
    return redirect("settings-automod")


@require_POST
@permission_required("bookwyrm.moderate_user", raise_exception=True)
@permission_required("bookwyrm.moderate_post", raise_exception=True)
# pylint: disable=unused-argument
def unschedule_automod_task(request, task_id):
    """unscheduler"""
    get_object_or_404(PeriodicTask, id=task_id).delete()
    return redirect("settings-automod")


@require_POST
@permission_required("bookwyrm.moderate_user", raise_exception=True)
@permission_required("bookwyrm.moderate_post", raise_exception=True)
# pylint: disable=unused-argument
def automod_delete(request, rule_id):
    """Remove a rule"""
    get_object_or_404(models.AutoMod, id=rule_id).delete()
    return redirect("settings-automod")


@require_POST
@permission_required("bookwyrm.moderate_user", raise_exception=True)
@permission_required("bookwyrm.moderate_post", raise_exception=True)
# pylint: disable=unused-argument
def run_automod(request):
    """run scan"""
    models.automod_task.delay()
    return redirect("settings-automod")


def automod_view_data():
    """helper to get data used in the template"""
    try:
        task = PeriodicTask.objects.get(name="automod-task")
    except PeriodicTask.DoesNotExist:
        task = None

    return {
        "task": task,
        "task_form": forms.IntervalScheduleForm(),
        "rules": models.AutoMod.objects.all(),
        "form": forms.AutoModRuleForm(),
    }
