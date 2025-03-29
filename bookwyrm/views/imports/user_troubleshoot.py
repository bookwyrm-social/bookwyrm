""" import books from another app """
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.views import View

from bookwyrm import models
from bookwyrm.importers import BookwyrmImporter
from bookwyrm.views import user_import_available
from bookwyrm.settings import PAGE_LENGTH

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class UserImportTroubleshoot(View):
    """failed items in an existing user import"""

    def get(self, request, job_id):
        """status of an import job"""
        job = get_object_or_404(models.BookwyrmImportJob, id=job_id)
        if job.user != request.user:
            raise PermissionDenied()

        items = job.child_jobs.order_by("task_id").filter(status="failed")
        paginated = Paginator(items, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "next_available": user_import_available(user=request.user),
            "job": job,
            "items": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "complete": True,
            "page_path": reverse("user-import-troubleshoot", args=[job.id]),
        }

        return TemplateResponse(request, "import/user_troubleshoot.html", data)

    def post(self, request, job_id):
        """retry lines from a user import"""
        job = get_object_or_404(models.BookwyrmImportJob, id=job_id)

        importer = BookwyrmImporter()
        job = importer.create_retry_job(request.user, job)
        job.start_job()
        return redirect(f"/user-import/{job.id}")
