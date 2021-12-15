""" import books from another app """
from io import TextIOWrapper

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View

from bookwyrm import forms, models
from bookwyrm.importers import (
    LibrarythingImporter,
    GoodreadsImporter,
    StorygraphImporter,
    OpenLibraryImporter,
)

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

        importer.start_import(job)

        return redirect(f"/import/{job.id}")
