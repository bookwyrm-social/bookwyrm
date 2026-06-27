"""Data quality and deduplication"""

from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import forms, models


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class DataQuality(View):
    """deduplication task settings"""

    def get(self, request):
        """view maintenance task settings"""
        return TemplateResponse(request, "settings/data.html", data_quality_data())


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def schedule_deduplication_scan_task(request):
    """scheduler"""
    form = forms.IntervalScheduleForm(request.POST)
    if not form.is_valid():
        data = data_quality_data()
        data["scan_form"] = form
        return TemplateResponse(request, "settings/data.html", data)

    with transaction.atomic():
        schedule, _ = IntervalSchedule.objects.get_or_create(**form.cleaned_data)
        PeriodicTask.objects.get_or_create(
            interval=schedule,
            name="dedupe-scan-task",
            task="bookwyrm.models.housekeeping.mark_duplicate_data_task",
        )
    return redirect("settings-data-quality")


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def unschedule_deduplication_scan_task(request, task_id):
    """unscheduler"""
    get_object_or_404(PeriodicTask, id=task_id).delete()
    return redirect("settings-data-quality")


def data_quality_data():
    """helper to get data used in the template"""
    try:
        scan_task = PeriodicTask.objects.get(name="dedupe-scan-task")
    except PeriodicTask.DoesNotExist:
        scan_task = None

    return {
        "scan_task": scan_task,
        "work_count": models.Work.objects.filter(
            pending_merge_target__isnull=False
        ).count(),
        "work_example": models.Work.objects.filter(
            pending_merge_target__isnull=False
        ).first(),
        "edition_count": models.Edition.objects.filter(
            pending_merge_target__isnull=False
        ).count(),
        "edition_example": models.Edition.objects.filter(
            pending_merge_target__isnull=False
        ).first(),
        "author_count": models.Author.objects.filter(
            pending_merge_target__isnull=False
        ).count(),
        "author_example": models.Author.objects.filter(
            pending_merge_target__isnull=False
        ).first(),
        "series_count": models.Series.objects.filter(
            pending_merge_target__isnull=False
        ).count(),
        "series_example": models.Series.objects.filter(
            pending_merge_target__isnull=False
        ).first(),
        "task_form": forms.IntervalScheduleForm(),
    }
