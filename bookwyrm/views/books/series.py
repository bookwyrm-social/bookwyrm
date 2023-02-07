""" books belonging to the same series """
from sys import float_info
from django.views import View
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from bookwyrm.views.helpers import is_api_request
from bookwyrm import models


def sort_by_series(book):
    """sort books using their series number"""
    try:
        return float(book.series_number)
    except ValueError:
        return float_info.max


# pylint: disable=no-self-use
class BookSeriesBy(View):
    """book series by author"""

    def get(self, request, author_id):
        """lists all books in a series"""
        series_name = request.GET.get("series_name")

        if is_api_request(request):
            pass

        author = get_object_or_404(models.Author, id=author_id)

        results = models.Edition.objects.filter(authors=author, series=series_name)

        # when there are multiple editions of the same work
        # pick the one with a series number or closest
        work_ids = results.values_list("parent_work__id", flat=True).distinct()

        # filter out multiple editions of the same work
        numbered_books = []
        dated_books = []
        unsortable_books = []
        for work_id in set(work_ids):
            result = (
                results.filter(parent_work=work_id)
                .order_by("series_number", "-edition_rank")
                .first()
            )
            if result.series_number:
                numbered_books.append(result)
            elif result.first_published_date or result.published_date:
                dated_books.append(result)
            else:
                unsortable_books.append(result)

        list_results = (
            sorted(numbered_books, key=sort_by_series)
            + sorted(
                dated_books,
                key=lambda book: book.first_published_date
                if book.first_published_date
                else book.published_date,
            )
            + sorted(
                unsortable_books,
                key=lambda book: book.sort_title if book.sort_title else book.title,
            )
        )

        data = {
            "series_name": series_name,
            "author": author,
            "books": list_results,
        }

        return TemplateResponse(request, "book/series.html", data)
