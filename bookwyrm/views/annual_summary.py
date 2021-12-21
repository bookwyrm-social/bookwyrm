from datetime import date

from django.db.models import Case, When, Avg, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import models


# December day of first availability
FIRST_DAY = 15


def is_year_available(year):
    """return boolean"""

    today = date.today()
    year = int(year)
    if year < today.year:
        return True
    if year == today.year and today >= date(today.year, 12, FIRST_DAY):
        return True

    return False


class AnnualSummary(View):
    """display a summary of the year for the current user"""

    def get(self, request, year):
        """get response"""

        if not is_year_available(year):
            raise Http404(f"The summary for {year} is unavailable")

        user = request.user
        read_shelf = get_object_or_404(user.shelf_set, identifier="read")
        read_book_ids_in_year = (
            models.ShelfBook.objects.filter(shelf=read_shelf)
            .filter(user=user)
            .filter(shelved_date__year=year)
            .order_by("shelved_date", "created_date", "updated_date")
            .values_list("book", flat=True)
        )
        read_shelf_order = Case(
            *[When(pk=pk, then=pos) for pos, pk in enumerate(read_book_ids_in_year)]
        )
        read_books_in_year = models.Edition.objects.filter(
            id__in=read_book_ids_in_year
        ).order_by(read_shelf_order)

        """pages stats queries"""
        page_stats = read_books_in_year.aggregate(Sum("pages"), Avg("pages"))
        book_list_by_pages = read_books_in_year.filter(pages__gte=0).order_by("pages")
        book_pages_lowest = book_list_by_pages.first()
        book_pages_highest = book_list_by_pages.last()

        """books with no pages"""
        no_page_list = len(read_books_in_year.filter(pages__exact=None))

        """rating stats queries"""
        ratings = (
            models.Review.objects.filter(user=user)
            .exclude(deleted=True)
            .exclude(rating=None)
            .filter(book_id__in=read_book_ids_in_year)
        )
        best_ratings_books_ids = [review.book.id for review in ratings.filter(rating=5)]
        ratings_stats = ratings.aggregate(Avg("rating"))

        paginated_years = (
            int(year) - 1,
            int(year) + 1 if is_year_available(int(year) + 1) else None
        )

        data = {
            "year": year,
            "books_total": len(read_books_in_year),
            "books": read_books_in_year,
            "pages_total": page_stats["pages__sum"],
            "pages_average": page_stats["pages__avg"],
            "book_pages_lowest": book_pages_lowest,
            "book_pages_highest": book_pages_highest,
            "no_page_number": no_page_list,
            "ratings_total": len(ratings),
            "rating_average": ratings_stats["rating__avg"],
            "book_rating_highest": ratings.order_by("-rating").first(),
            "best_ratings_books_ids": best_ratings_books_ids,
            "paginated_years": paginated_years,
        }

        return TemplateResponse(request, "annual_summary/layout.html", data)
