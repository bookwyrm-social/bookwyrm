""" import books from another app """
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.importers import GoodreadsImporter
from bookwyrm.models.import_job import import_item_task
from bookwyrm.settings import PAGE_LENGTH

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class ImportStatus(View):
    """status of an existing import"""

    def get(self, request, job_id):
        """status of an import job"""
        job = get_object_or_404(models.ImportJob, id=job_id)
        if job.user != request.user:
            raise PermissionDenied()

        items = job.items.order_by("index")
        item_count = items.count() or 1

        paginated = Paginator(items, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        manual_review_count = items.filter(
            fail_reason__isnull=False, book_guess__isnull=False, book__isnull=True
        ).count()
        fail_count = items.filter(
            fail_reason__isnull=False, book_guess__isnull=True
        ).count()
        pending_item_count = job.pending_item_count
        data = {
            "job": job,
            "items": page,
            "manual_review_count": manual_review_count,
            "fail_count": fail_count,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "show_progress": True,
            "item_count": item_count,
            "complete_count": item_count - pending_item_count,
            "percent": job.percent_complete,
            # hours since last import item update
            "inactive_time": (job.updated_date - timezone.now()).seconds / 60 / 60,
            "legacy": not job.mappings,
        }

        return TemplateResponse(request, "import/import_status.html", data)

    def post(self, request, job_id):
        """bring a legacy import into the latest format"""
        job = get_object_or_404(models.ImportJob, id=job_id)
        if job.user != request.user:
            raise PermissionDenied()
        GoodreadsImporter().update_legacy_job(job)
        return redirect("import-status", job_id)


@login_required
@require_POST
def retry_item(request, job_id, item_id):
    """retry an item"""
    item = get_object_or_404(
        models.ImportItem, id=item_id, job__id=job_id, job__user=request.user
    )
    import_item_task.delay(item.id)
    return redirect("import-status", job_id)


@login_required
@require_POST
def stop_import(request, job_id):
    """scrap that"""
    job = get_object_or_404(models.ImportJob, id=job_id, user=request.user)
    job.stop_job()
    return redirect("import-status", job_id)
