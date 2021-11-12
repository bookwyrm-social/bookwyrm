""" import books from another app """
from io import TextIOWrapper
import math

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View

from bookwyrm import forms, models
from bookwyrm.importers import (
    Importer,
    LibrarythingImporter,
    GoodreadsImporter,
    StorygraphImporter,
)
from bookwyrm.settings import PAGE_LENGTH

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Import(View):
    """import view"""

    def get(self, request):
        """load import page"""
        return TemplateResponse(
            request,
            "import/import.html",
            {
                "import_form": forms.ImportForm(),
                "jobs": models.ImportJob.objects.filter(user=request.user).order_by(
                    "-created_date"
                ),
            },
        )

    def post(self, request):
        """ingest a goodreads csv"""
        form = forms.ImportForm(request.POST, request.FILES)
        if form.is_valid():
            include_reviews = request.POST.get("include_reviews") == "on"
            privacy = request.POST.get("privacy")
            source = request.POST.get("source")

            importer = None
            if source == "LibraryThing":
                importer = LibrarythingImporter()
            elif source == "Storygraph":
                importer = StorygraphImporter()
            else:
                # Default : Goodreads
                importer = GoodreadsImporter()

            try:
                job = importer.create_job(
                    request.user,
                    TextIOWrapper(
                        request.FILES["csv_file"], encoding=importer.encoding
                    ),
                    include_reviews,
                    privacy,
                )
            except (UnicodeDecodeError, ValueError, KeyError):
                return HttpResponseBadRequest(_("Not a valid csv file"))

            importer.start_import(job)

            return redirect(f"/import/{job.id}")
        return HttpResponseBadRequest()


@method_decorator(login_required, name="dispatch")
class ImportStatus(View):
    """status of an existing import"""

    def get(self, request, job_id):
        """status of an import job"""
        job = get_object_or_404(models.ImportJob, id=job_id)
        if job.user != request.user:
            raise PermissionDenied()

        items = job.items.order_by("index")
        pending_items = items.filter(fail_reason__isnull=True, book__isnull=True)
        item_count = items.count() or 1

        paginated = Paginator(items, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "job": job,
            "items": page,
            "fail_count": items.filter(fail_reason__isnull=False).count(),
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "complete": not pending_items.exists(),
            "percent": math.floor(  # pylint: disable=c-extension-no-member
                (item_count - pending_items.count()) / item_count * 100
            ),
        }

        return TemplateResponse(request, "import/import_status.html", data)


@method_decorator(login_required, name="dispatch")
class ImportTroubleshoot(View):
    """problems items in an existing import"""

    def get(self, request, job_id):
        """status of an import job"""
        job = get_object_or_404(models.ImportJob, id=job_id)
        if job.user != request.user:
            raise PermissionDenied()

        items = job.items.order_by("index").filter(fail_reason__isnull=False)

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
