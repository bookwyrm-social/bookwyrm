""" import books from another app """
from io import TextIOWrapper
import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, ExpressionWrapper, F, fields
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.importers import (
    BookwyrmImporter,
    CalibreImporter,
    LibrarythingImporter,
    GoodreadsImporter,
    StorygraphImporter,
    OpenLibraryImporter,
)
from bookwyrm.models.bookwyrm_import_job import BookwyrmImportJob
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.utils.cache import get_or_set

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Import(View):
    """import view"""

    def get(self, request, invalid=False):
        """load import page"""
        jobs = models.ImportJob.objects.filter(user=request.user).order_by(
            "-created_date"
        )
        paginated = Paginator(jobs, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "import_form": forms.ImportForm(),
            "jobs": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "invalid": invalid,
        }

        seconds = get_or_set("avg-import-time", get_average_import_time, timeout=86400)
        if seconds and seconds > 60**2:
            data["recent_avg_hours"] = seconds / (60**2)
        elif seconds:
            data["recent_avg_minutes"] = seconds / 60

        site_settings = models.SiteSettings.objects.get()
        time_range = timezone.now() - datetime.timedelta(
            days=site_settings.import_limit_reset
        )
        import_jobs = models.ImportJob.objects.filter(
            user=request.user, created_date__gte=time_range
        )
        # pylint: disable=consider-using-generator
        imported_books = sum([job.successful_item_count for job in import_jobs])
        data["import_size_limit"] = site_settings.import_size_limit
        data["import_limit_reset"] = site_settings.import_limit_reset
        data["allowed_imports"] = site_settings.import_size_limit - imported_books

        return TemplateResponse(request, "import/import.html", data)

    def post(self, request):
        """ingest a goodreads csv"""
        site = models.SiteSettings.objects.get()
        if not site.imports_enabled:
            raise PermissionDenied()

        form = forms.ImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponseBadRequest()

        include_reviews = request.POST.get("include_reviews") == "on"
        privacy = request.POST.get("privacy")
        source = request.POST.get("source")

        importer = None
        if source == "LibraryThing":
            importer = LibrarythingImporter()
        elif source == "Storygraph":
            importer = StorygraphImporter()
        elif source == "OpenLibrary":
            importer = OpenLibraryImporter()
        elif source == "Calibre":
            importer = CalibreImporter()
        else:
            # Default : Goodreads
            importer = GoodreadsImporter()

        try:
            job = importer.create_job(
                request.user,
                TextIOWrapper(request.FILES["csv_file"], encoding=importer.encoding),
                include_reviews,
                privacy,
            )
        except (UnicodeDecodeError, ValueError, KeyError):
            return self.get(request, invalid=True)

        job.start_job()

        return redirect(f"/import/{job.id}")


def get_average_import_time() -> float:
    """Helper to figure out how long imports are taking (returns seconds)"""
    last_week = timezone.now() - datetime.timedelta(days=7)
    recent_avg = (
        models.ImportJob.objects.filter(created_date__gte=last_week, complete=True)
        .exclude(status="stopped")
        .annotate(
            runtime=ExpressionWrapper(
                F("updated_date") - F("created_date"),
                output_field=fields.DurationField(),
            )
        )
        .aggregate(Avg("runtime"))
        .get("runtime__avg")
    )

    if recent_avg:
        return recent_avg.total_seconds()
    return None


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class UserImport(View):
    """import user view"""

    def get(self, request, invalid=False):
        """load user import page"""

        jobs = BookwyrmImportJob.objects.filter(user=request.user).order_by(
            "-created_date"
        )
        site = models.SiteSettings.objects.get()
        hours = site.user_import_time_limit
        allowed = (
            jobs.first().created_date < timezone.now() - datetime.timedelta(hours=hours)
            if jobs.first()
            else True
        )
        next_available = (
            jobs.first().created_date + datetime.timedelta(hours=hours)
            if not allowed
            else False
        )
        paginated = Paginator(jobs, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "import_form": forms.ImportUserForm(),
            "jobs": page,
            "user_import_hours": hours,
            "next_available": next_available,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "invalid": invalid,
        }

        return TemplateResponse(request, "import/import_user.html", data)

    def post(self, request):
        """ingest a Bookwyrm json file"""

        importer = BookwyrmImporter()

        form = forms.ImportUserForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponseBadRequest()

        job = importer.process_import(
            user=request.user,
            archive_file=request.FILES["archive_file"],
            settings=request.POST,
        )

        job.start_job()

        return redirect("user-import")
