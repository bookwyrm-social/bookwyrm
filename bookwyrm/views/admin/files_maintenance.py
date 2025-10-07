""" clean up export files and find book covers """
import json

from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import forms, models

# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class FilesMaintenance(View):
    """maintenance task settings"""

    def get(self, request):
        """view maintenance task settings"""
        return TemplateResponse(
            request, "settings/files.html", files_maintenance_data()
        )


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def schedule_export_delete_task(request):
    """scheduler"""
    form = forms.IntervalScheduleForm(request.POST)
    if not form.is_valid():
        data = files_maintenance_data()
        data["task_form"] = form
        return TemplateResponse(request, "settings/files.html", data)

    with transaction.atomic():
        schedule, _ = IntervalSchedule.objects.get_or_create(**form.cleaned_data)
        PeriodicTask.objects.get_or_create(
            interval=schedule,
            name="delete-exports-task",
            task="bookwyrm.models.housekeeping.start_export_deletions",
            kwargs=json.dumps({"user": request.user.id}),
        )
    return redirect("settings-files")


# pylint: disable=unused-argument
@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def unschedule_export_delete_task(request, task_id):
    """unscheduler"""
    get_object_or_404(PeriodicTask, id=task_id).delete()
    return redirect("settings-files")


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def run_export_deletions(request):
    """run scan"""
    models.start_export_deletions.delay(user=request.user.id)
    return redirect("settings-files")


# pylint: disable=unused-argument
@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def cancel_export_delete_job(request, job_id):
    """unscheduler"""
    get_object_or_404(
        models.housekeeping.CleanUpUserExportFilesJob, id=job_id
    ).stop_job()
    return redirect("settings-files")


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def set_export_expiry_age(request):
    """set the age limit for user export files"""

    form = forms.ExportFileExpiryForm(request.POST)
    if not form.is_valid():
        data = files_maintenance_data()
        data["expiry_form"] = form
        return TemplateResponse(request, "settings/files.html", data)

    site = models.SiteSettings.objects.get()
    site.export_files_lifetime_hours = form.cleaned_data["hours"]
    site.save(update_fields=["export_files_lifetime_hours"])
    data = files_maintenance_data()
    data["success"] = True
    return TemplateResponse(request, "settings/files.html", data)


def files_maintenance_data():
    """helper to get data used in the template"""
    try:
        delete_task = PeriodicTask.objects.get(name="delete-exports-task")
    except PeriodicTask.DoesNotExist:
        delete_task = None

    site = models.SiteSettings.objects.get()
    delete_jobs = models.housekeeping.CleanUpUserExportFilesJob.objects.all().order_by(
        "-created_date"
    )[:5]

    return {
        "delete_task": delete_task,
        "delete_jobs": delete_jobs,
        "task_form": forms.IntervalScheduleForm(),
        "expiry_form": forms.ExportFileExpiryForm(),
        "max_hours": site.export_files_lifetime_hours,
    }
