""" import books from another app """
from io import TextIOWrapper
import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, ExpressionWrapper, F, fields
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View

from bookwyrm import forms, models
from bookwyrm.importers import (
    CalibreImporter,
    LibrarythingImporter,
    GoodreadsImporter,
    StorygraphImporter,
    OpenLibraryImporter,
)
from bookwyrm.settings import PAGE_LENGTH

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Import(View):
    """import view"""

    def get(self, request):
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
        }

        last_week = timezone.now() - datetime.timedelta(days=7)
        recent_avg = (
            models.ImportJob.objects.filter(created_date__gte=last_week, complete=True)
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
            seconds = recent_avg.total_seconds()
            if seconds > 60**2:
                data["recent_avg_hours"] = recent_avg.seconds / (60**2)
            else:
                data["recent_avg_minutes"] = recent_avg.seconds / 60

        return TemplateResponse(request, "import/import.html", data)

    def post(self, request):
        """ingest a goodreads csv"""
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
            return HttpResponseBadRequest(_("Not a valid csv file"))

        job.start_job()

        return redirect(f"/import/{job.id}")
