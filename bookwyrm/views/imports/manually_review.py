""" verify books we're unsure about """
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.models.import_job import import_item_task
from bookwyrm.settings import PAGE_LENGTH

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class ImportManualReview(View):
    """problems items in an existing import"""

    def get(self, request, job_id):
        """status of an import job"""
        job = get_object_or_404(models.ImportJob, id=job_id)
        if job.user != request.user:
            raise PermissionDenied()

        items = job.items.order_by("index").filter(
            book__isnull=True, book_guess__isnull=False
        )

        paginated = Paginator(items, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "job": job,
            "items": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "complete": True,
        }

        return TemplateResponse(request, "import/manual_review.html", data)


@login_required
@require_POST
# pylint: disable=unused-argument
def approve_import_item(request, job_id, item_id):
    """we guessed right"""
    item = get_object_or_404(
        models.ImportItem, id=item_id, job__id=job_id, book_guess__isnull=False
    )
    item.fail_reason = None
    item.book = item.book_guess
    item.book_guess = None
    item.save()

    # the good stuff - actually import the data
    import_item_task.delay(item.id)
    return redirect("import-review", job_id)


@login_required
@require_POST
# pylint: disable=unused-argument
def delete_import_item(request, job_id, item_id):
    """we guessed right"""
    item = get_object_or_404(
        models.ImportItem, id=item_id, job__id=job_id, book_guess__isnull=False
    )
    item.book_guess = None
    item.save()
    return redirect("import-review", job_id)
