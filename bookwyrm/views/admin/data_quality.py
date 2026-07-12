"""Data quality and deduplication"""

from datetime import datetime
import difflib
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.db import transaction
from django.apps import apps
from django.http import Http404
from bookwyrm.settings import PAGE_LENGTH
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
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
        return TemplateResponse(
            request, "settings/manage-data/data.html", data_quality_data()
        )


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def run_deduplication_scan_task(request):
    """run now"""
    models.housekeeping.mark_duplicate_data_task.delay()
    return redirect("settings-data-quality")


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


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.manage_data", raise_exception=True),
    name="dispatch",
)
class MergeData(View):
    """deduplication tasks"""

    def get(self, request):
        """view deduplication tasks"""

        data = {
            "works_count": models.Work.objects.filter(merge_target__isnull=False)
            .distinct()
            .count(),
            "editions_count": models.Edition.objects.filter(merge_target__isnull=False)
            .distinct()
            .count(),
            "authors_count": models.Author.objects.filter(merge_target__isnull=False)
            .distinct()
            .count(),
            "series_count": models.Series.objects.filter(merge_target__isnull=False)
            .distinct()
            .count(),
        }

        match request.GET.get("merge_type"):
            case "work":
                items = (
                    models.Work.objects.filter(merge_target__isnull=False)
                    .annotate(targets=Count("merge_target"))
                    .order_by("-targets")
                    .order_by("title")
                )
                paginated = Paginator(items, PAGE_LENGTH)
                data["works"] = paginated.get_page(request.GET.get("page"))
            case "author":
                items = (
                    models.Author.objects.filter(merge_target__isnull=False)
                    .annotate(targets=Count("merge_target"))
                    .order_by("-targets")
                    .order_by("name")
                )
                paginated = Paginator(items, PAGE_LENGTH)
                data["authors"] = paginated.get_page(request.GET.get("page"))
            case "series":
                items = (
                    models.Series.objects.filter(merge_target__isnull=False)
                    .annotate(targets=Count("merge_target"))
                    .order_by("-targets")
                    .order_by("name")
                )
                paginated = Paginator(items, PAGE_LENGTH)
                data["series"] = paginated.get_page(request.GET.get("page"))
            case _:
                items = (
                    models.Edition.objects.filter(merge_target__isnull=False)
                    .annotate(targets=Count("merge_target"))
                    .order_by("-targets")
                    .order_by("title")
                )
                paginated = Paginator(items, PAGE_LENGTH)
                data["editions"] = paginated.get_page(request.GET.get("page"))
        return TemplateResponse(request, "settings/manage-data/merge.html", data)


def get_diff_string(canonical: str, candidate: str, array=False) -> str:
    """create and return a diff string for object fields"""

    canonical = str(canonical) if type(canonical) is int else canonical or ""
    candidate = str(candidate) if type(candidate) is int else candidate or ""
    diff = difflib.Differ()
    delta = list(diff.compare(canonical, candidate))
    string = []

    for word in delta:
        match word[0]:
            case "+":
                string += f"<span class='has-background-success-light has-text-success has-text-weight-semibold'>{word[2:]}</span>"
            case "-":
                if not array:
                    string += f"<span class='has-background-danger-light has-text-danger has-text-weight-semibold'><strike>{word[2:]}</strike></span>"
            case _:
                string += word[2:]
    return "".join(string)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.manage_data", raise_exception=True),
    name="dispatch",
)
class ManualMerge(View):
    """Merge objects"""

    def get(self, request, model_name, canonical_id):
        """View merge objects page"""

        model = apps.get_model(f"bookwyrm.{model_name}", require_ready=True)
        plural_model = model._meta.verbose_name_plural
        canonical = get_object_or_404(model.objects.filter(id=canonical_id))
        candidates = canonical.merge_candidates
        if not candidates:
            raise Http404

        ids = list(candidates.values_list("id", flat=True))
        ids.append(canonical.id)
        all_objects = model.objects.filter(id__in=ids)

        simple_fields = []
        array_fields = []
        datetime_fields = [
            "first_published_date",
            "published_date",
            "born",
            "died",
        ]

        for field in candidates.model._meta.get_fields():
            if (
                field.name in ["remote_id", "origin_id", "sort_title", "edition_rank"]
                or "date_precision" in field.name
            ):
                continue
            if (
                candidates.model._meta.get_field(field.name).get_internal_type()
                in [
                    "CharField",
                    "TextField",
                    "IntegerField",
                ]
                or field.name in datetime_fields
            ):
                all_vals = [getattr(x, field.name) for x in candidates]
                if any(all_vals) and not all(
                    val == getattr(canonical, field.name) for val in all_vals
                ):
                    values = []
                    for obj in candidates:
                        if value := getattr(obj, field.name):
                            if value not in values:
                                values.append(value)
                    simple_fields.append(
                        {
                            "name": field.name,
                            "trans_name": _(field.name),
                            "values": values,
                        }
                    )
            if (
                candidates.model._meta.get_field(field.name).get_internal_type()
                == "ArrayField"
            ):
                if any([getattr(x, field.name) for x in candidates]):
                    values = []
                    for obj in candidates:
                        if array := getattr(obj, field.name):
                            for value in array:
                                if value not in values:
                                    values.append(value)
                    array_fields.append(
                        {
                            "name": field.name,
                            "trans_name": _(field.name),
                            "values": values,
                        }
                    )

        data = {
            "simple_fields": simple_fields,
            "array_fields": array_fields,
            "datetime_fields": datetime_fields,
            "canonical": canonical,
            "objects": all_objects.reverse(),
            "model_name": model_name,
            "plural_model": plural_model,
            "source": request.GET.get("source"),
        }
        return TemplateResponse(request, "settings/manage-data/manual-merge.html", data)

    def post(self, request, model_name, canonical_id):
        """receiving a form submission"""

        model = apps.get_model(f"bookwyrm.{model_name}", require_ready=True)
        canonical = get_object_or_404(model.objects.filter(id=canonical_id))
        update_fields = [
            field for field in request.POST if field != "csrfmiddlewaretoken"
        ]
        update_fields.sort()
        fields_obj = {field: {"name": field} for field in update_fields}
        array_fields = []

        for field in update_fields:
            if model._meta.get_field(field).get_internal_type() == "DateTimeField":
                canonical_date = (
                    getattr(canonical, field).strftime("%Y-%m-%d")
                    if getattr(canonical, field)
                    else ""
                )
                merged_date = request.POST[field] if request.POST.get(field) else ""
                diff = get_diff_string(canonical_date, merged_date)
                value = request.POST.get(field)
            elif model._meta.get_field(field).get_internal_type() == "ArrayField":
                for f in set(request.POST.getlist(field)):
                    obj = {
                        "name": field,
                        "value": f,
                        "diff": get_diff_string(
                            getattr(canonical, field), [f], array=True
                        ),
                    }
                    array_fields.append(obj)
                del fields_obj[field]
                continue
            else:
                diff = get_diff_string(
                    getattr(canonical, field), request.POST.get(field)
                )
                value = request.POST.get(field)

            fields_obj[field]["diff"] = diff
            fields_obj[field]["value"] = value
        fields = [fields_obj[key] for key in fields_obj]

        data = {
            "update_fields": update_fields,
            "fields": fields + array_fields,
            "model_name": model_name,
            "canonical_id": canonical.id,
            "source": request.GET.get("source"),
        }
        return TemplateResponse(
            request, "settings/manage-data/confirm-merge.html", data
        )


@require_POST
@permission_required("bookwyrm.manage_data", raise_exception=True)
def confirm_manual_merge(request, model_name, canonical_id):
    """receiving a manual merge confirmation"""

    model = apps.get_model(f"bookwyrm.{model_name}", require_ready=True)
    canonical = get_object_or_404(model.objects.filter(id=canonical_id))
    update_fields = [field for field in request.POST if field != "csrfmiddlewaretoken"]

    if update_fields:
        for field in update_fields:
            value = request.POST.get(field)
            if model._meta.get_field(field).get_internal_type() == "DateTimeField":
                value = datetime.fromisoformat(f"{value}T12:00:00Z")
            if model._meta.get_field(field).get_internal_type() == "ArrayField":
                value = request.POST.getlist(field)
            setattr(canonical, field, value)
        canonical.save(update_fields=update_fields)

    for candidate in canonical.merge_candidates:
        candidate.merge_into(canonical, manual=True)

    if request.GET.get("source") == "admin":
        return redirect(reverse("settings-merge-data"))
    return redirect(canonical.remote_id)
