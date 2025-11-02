"""book series"""

from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.decorators.vary import vary_on_headers

from bookwyrm.forms import SeriesForm
from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import (
    is_api_request,
    get_mergeable_object_or_404,
)


class Series(View):
    """a series of books"""

    # pylint: disable=unused-argument,no-self-use
    @vary_on_headers("Accept")
    def get(self, request, series_id, slug=None):
        """landing page for a series"""
        series = get_mergeable_object_or_404(models.Series, id=series_id)

        if is_api_request(request):
            return ActivitypubResponse(series.to_activity(**request.GET))

        authors = models.Author.objects.none()
        books = []
        items = (
            series.seriesbooks.filter(series=series.id)
            .prefetch_related("book", "book__authors")
            .order_by("series_number")
        )
        for item in items:

            book = (
                item.book.edition
                if hasattr(item.book, "edition")
                else item.book.work.default_edition
            )

            book_data = {"book": book, "series_number": item.series_number}
            books.append(book_data)

            authors = authors.union(item.book.authors.all())

        paginated = Paginator(items, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))

        data = {
            "series": series,
            "books": page,
            "series_authors": {"authors": authors},
        }

        return TemplateResponse(request, "book/series.html", data)


class EditSeries(View):
    """Edit information about series and seriesbooks"""

    # pylint: disable=no-self-use
    def get(self, request, series_id=None):
        """edit page for series"""

        series = models.Series.objects.filter(id=series_id).first()
        seriesbooks = models.SeriesBook.objects.filter(series=series)
        data = {
            "series": series,
            "books": seriesbooks,
            "form": SeriesForm(instance=series),
        }

        return TemplateResponse(request, "book/edit/edit_series.html", data)

    # pylint: disable=no-self-use
    def post(self, request, series_id):
        """submit the series edit form"""

        form = SeriesForm(request.POST)
        data = {"form": form}

        if not form.is_valid():
            # TODO do we need to persist seriesbook data also?
            print("not valid")
            print(form.errors)
            return TemplateResponse(request, "book/edit/edit_series.html", data)

        instance = models.Series.objects.get(id=series_id)
        form = SeriesForm(request.POST, instance=instance)
        series = form.save(request)
        alt_titles = []
        for title in request.POST.getlist("alternative_titles"):
            if title != "":
                alt_titles.append(title)
        series.alternative_titles = alt_titles
        series.save(update_fields=["alternative_titles"])

        # update seriesbooks as needed
        for book in series.seriesbooks.all():
            value = request.POST[f"series_number-{book.id}"]
            book.series_number = value
            # save the series_number as the value
            book.save(update_fields=["series_number"])

        return redirect("series", series_id)


class SeriesBook(View):
    """a book in a series"""

    # pylint: disable=no-self-use
    @vary_on_headers("Accept")
    def get(self, request, seriesbook_id):
        """we just need this for resolving AP requests"""
        seriesbook = get_mergeable_object_or_404(models.SeriesBook, id=seriesbook_id)

        if is_api_request(request):
            return ActivitypubResponse(seriesbook.to_activity())

        raise Http404()
