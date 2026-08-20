"""book series"""

from django.core.paginator import Paginator
from django.db.utils import IntegrityError
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.vary import vary_on_headers
from django_celery_beat.models import PeriodicTask

from bookwyrm.forms import SeriesForm
from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import (
    is_api_request,
    get_mergeable_object_or_404,
)
from bookwyrm.views.mixins import MergeableViewMixin


class Series(MergeableViewMixin, View):
    """a series of books"""

    merge_model = models.Series

    @vary_on_headers("Accept")
    def get(self, request, series_id, slug=None):
        """landing page for a series"""
        series = get_mergeable_object_or_404(models.Series, id=series_id)

        if is_api_request(request):
            return ActivitypubResponse(series.to_activity(**request.GET))

        blocked = request.user.blocked_books.all() if request.user else []
        items = series.seriesbooks.exclude(book__in=blocked).prefetch_related(
            "book__work", "book__work__editions__authors"
        )
        series_books = sorted(items, key=lambda sb: sb.natural_sort_key)
        authors = models.Author.objects.filter(
            id__in=items.values_list("book__work__editions__authors")
        )

        paginated = Paginator(series_books, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))

        merge_scheduled = PeriodicTask.objects.filter(name="dedupe-merge-task").exists()
        data = {
            "series": series,
            "series_dupe": series.pending_merge_target,
            "merge_scheduled": merge_scheduled,
            "series_books": page,
            "series_authors": {"authors": authors},
        }

        return TemplateResponse(request, "book/series.html", data)


class EditSeries(View):
    """Edit information about series and seriesbooks"""

    def get(self, request, series_id=None):
        """edit page for series"""

        series = models.Series.objects.get(id=series_id)
        data = {"series": series, "form": SeriesForm(instance=series)}

        return TemplateResponse(request, "book/edit/edit_series.html", data)

    def post(self, request, series_id):
        """submit the series edit form"""

        series = get_mergeable_object_or_404(models.Series, id=series_id)
        form = SeriesForm(request.POST, instance=series)
        data = {"series": series, "form": form}

        if not form.is_valid():
            return TemplateResponse(request, "book/edit/edit_series.html", data)

        series = form.save(request)
        alt_names = []
        for a_name in request.POST.getlist("alternative_names"):
            if a_name != "":
                alt_names.append(a_name)
        series.alternative_names = alt_names
        series.save(update_fields=["alternative_names"])

        seriesbook_errors = []
        for book in series.seriesbooks.all():
            if value := request.POST.get(f"series_number-{book.book.id}"):
                try:
                    book.series_number = value
                    book.save(update_fields=["series_number"])
                except IntegrityError as e:
                    if "duplicate key value violates unique constraint" in str(e):
                        error = _("Series position must be unique for each book")
                    else:
                        error = e
                    seriesbook_errors.append(error)
        if len(seriesbook_errors) > 0:
            data["seriesbook_errors"] = seriesbook_errors
            return TemplateResponse(request, "book/edit/edit_series.html", data)

            value = request.POST[f"series_number-{book.book.id}"]
            book.series_number = value
            # save the series_number as the value
            book.save(update_fields=["series_number"])

        return redirect(series.local_path)


class SeriesBook(View):
    """a book in a series"""

    @vary_on_headers("Accept")
    def get(self, request, seriesbook_id):
        """we just need this for resolving AP requests"""

        seriesbook = get_mergeable_object_or_404(models.SeriesBook, id=seriesbook_id)

        if is_api_request(request):
            return ActivitypubResponse(seriesbook.to_activity())

        raise Http404()
