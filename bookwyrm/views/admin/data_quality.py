"""Data quality and deduplication"""

from datetime import datetime
import difflib
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.apps import apps
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.http import require_POST
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import forms


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
            request, "settings/data-quality/data.html", data_quality_data()
        )


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def schedule_deduplication_scan_task(request):
    """scheduler"""
    form = forms.IntervalScheduleForm(request.POST)
    if not form.is_valid():
        data = data_quality_data()
        data["task_form"] = form
        return TemplateResponse(request, "settings/data-quality/data.html", data)

    with transaction.atomic():
        schedule, _ = IntervalSchedule.objects.get_or_create(**form.cleaned_data)
        PeriodicTask.objects.get_or_create(
            interval=schedule,
            name="dedupe-task",
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
        dedupe_task = PeriodicTask.objects.get(name="dedupe-task")
    except PeriodicTask.DoesNotExist:
        dedupe_task = None

    return {
        "dedupe_task": dedupe_task,
        "task_form": forms.IntervalScheduleForm(),
    }


def get_diff_string(canonical: str, candidate: str, array=False) -> str:
    """create and return a diff string for object fields"""

    canonical = canonical or ""
    candidate = candidate or ""
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
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class ManualMerge(View):
    """Merge objects"""

    def get(self, request, model_name, canonical_id):
        """View merge objects page"""

        model = apps.get_model(
            f"bookwyrm.{model_name.capitalize()}", require_ready=True
        )
        canonical = get_object_or_404(model.objects.filter(id=canonical_id))
        candidates = canonical.merge_candidates
        if not candidates:
            raise Http404

        simple_fields = []
        array_fields = []
        for field in candidates.model._meta.get_fields():
            if (
                field.name in ["remote_id", "origin_id", "sort_title", "edition_rank"]
                or "date_precision" in field.name
            ):
                continue
            if candidates.model._meta.get_field(field.name).get_internal_type() in [
                "CharField",
                "TextField",
                "IntegerField",
            ] or field.name in [
                "first_published_date",
                "published_date",
                "born",
                "died",
            ]:
                all_vals = [getattr(x, field.name) for x in candidates]
                if any(all_vals) and not all(
                    val == getattr(canonical, field.name) for val in all_vals
                ):
                    simple_fields.append({"name": field.name, "trans_name": _(field.name)})
            if (
                candidates.model._meta.get_field(field.name).get_internal_type()
                == "ArrayField"
            ):
                if any([getattr(x, field.name) for x in candidates]):
                    array_fields.append({"name": field.name, "trans_name": _(field.name)})

        for field in simple_fields:
            value_kwargs = {f"{field['name']}__isnull": False}
            has_value = candidates.filter(**value_kwargs)
            if has_value.count() == 1 and getattr(canonical, field["name"]) is None or getattr(canonical, field["name"]) == "":
                field["unique"] = has_value.first().id
        objects = candidates.union(candidates.model.objects.filter(id=canonical.id))

        data = {
            "simple_fields": simple_fields,
            "array_fields": array_fields,
            "canonical": canonical,
            "objects": objects.reverse(),
            "model_name": model_name,
        }
        return TemplateResponse(
            request, "settings/data-quality/manual-merge.html", data
        )

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
                    obj = { "name": field, "value": f, "diff": get_diff_string(
                    getattr(canonical, field), [f], array=True
                    )}
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
            "model_name": model_name.capitalize(),
            "canonical_id": canonical.id,
        }
        return TemplateResponse(
            request, "settings/data-quality/confirm-merge.html", data
        )


@require_POST
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def confirm_manual_merge(request, model_name, canonical_id):
    """receiving a manual merge confirmation"""

    model = apps.get_model(f"bookwyrm.{model_name}", require_ready=True)
    canonical = get_object_or_404(model.objects.filter(id=canonical_id))
    update_fields = [field for field in request.POST if field != "csrfmiddlewaretoken"]

    for field in update_fields:
        value = request.POST.get(field)
        if model._meta.get_field(field).get_internal_type() == "DateTimeField":
            value = datetime.fromisoformat(f"{value}T12:00:00Z")
        if model._meta.get_field(field).get_internal_type() == "ArrayField":
            value = request.POST.getlist(field)

        setattr(canonical, field, value)
    canonical.save(update_fields=update_fields)

    for candidate in canonical.merge_candidates:
        candidate.merge_into(canonical)

    return redirect("settings-data-quality")
