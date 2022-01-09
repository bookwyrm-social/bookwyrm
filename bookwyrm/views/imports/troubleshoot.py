""" import books from another app """
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.importers import Importer
from bookwyrm.settings import PAGE_LENGTH

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class ImportTroubleshoot(View):
    """problems items in an existing import"""

    def get(self, request, job_id):
        """status of an import job"""
        job = get_object_or_404(models.ImportJob, id=job_id)
        if job.user != request.user:
            raise PermissionDenied()

        items = job.items.order_by("index").filter(
            fail_reason__isnull=False, book_guess__isnull=True
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

        return TemplateResponse(request, "import/troubleshoot.html", data)

    def post(self, request, job_id):
        """retry lines from an import"""
        job = get_object_or_404(models.ImportJob, id=job_id)
        items = job.items.filter(fail_reason__isnull=False)

        importer = Importer()
        job = importer.create_retry_job(
            request.user,
            job,
            items,
        )
        importer.start_import(job)
        return redirect(f"/import/{job.id}")
