"""end-of-year read books stats"""
from datetime import date
from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.db.models import Case, When, Avg, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from .helpers import get_user_from_username


# December day of first availability
FIRST_DAY = 15
# January day of last availability, 0 for no availability in Jan.
LAST_DAY = 15


# pylint: disable= no-self-use
class AnnualSummary(View):
    """display a summary of the year for the current user"""

    def get(self, request, username, year):
        """get response"""

        if not is_year_available(year):
            raise Http404(f"The summary for {year} is unavailable")

        paginated_years = (
            int(year) - 1,
            int(year) + 1 if is_year_available(int(year) + 1) else None,
        )

        user = get_user_from_username(request.user, username)

        year_key = None
        if user.summary_keys and year in user.summary_keys:
            year_key = user.summary_keys[year]

        # verify key
        if user != request.user:
            request_key = None
            if "key" in request.GET:
                request_key = request.GET["key"]

            if not request_key or request_key != year_key:
                raise Http404(f"The summary for {year} is unavailable")

        # get data
        read_book_ids_in_year = get_read_book_ids_in_year(user, year)

        if len(read_book_ids_in_year) == 0:
            data = {
                "summary_user": user,
                "year": year,
                "year_key": year_key,
                "book_total": 0,
                "books": [],
                "paginated_years": paginated_years,
            }
            return TemplateResponse(request, "annual_summary/layout.html", data)

        read_books_in_year = get_books_from_shelfbooks(read_book_ids_in_year)

        # pages stats queries
        page_stats = read_books_in_year.aggregate(Sum("pages"), Avg("pages"))
        book_list_by_pages = read_books_in_year.filter(pages__gte=0).order_by("pages")

        # books with no pages
        no_page_list = len(read_books_in_year.filter(pages__exact=None))

        # rating stats queries
        ratings = (
            models.Review.objects.filter(user=user)
            .exclude(deleted=True)
            .exclude(rating=None)
            .filter(book_id__in=read_book_ids_in_year)
        )
        ratings_stats = ratings.aggregate(Avg("rating"))

        data = {
            "summary_user": user,
            "year": year,
            "year_key": year_key,
            "books_total": len(read_books_in_year),
            "books": read_books_in_year,
            "pages_total": page_stats["pages__sum"],
            "pages_average": round(
                page_stats["pages__avg"] if page_stats["pages__avg"] else 0
            ),
            "book_pages_lowest": book_list_by_pages.first(),
            "book_pages_highest": book_list_by_pages.last(),
            "no_page_number": no_page_list,
            "ratings_total": len(ratings),
            "rating_average": round(
                ratings_stats["rating__avg"] if ratings_stats["rating__avg"] else 0, 2
            ),
            "book_rating_highest": ratings.order_by("-rating").first(),
            "best_ratings_books_ids": [
                review.book.id for review in ratings.filter(rating=5)
            ],
            "paginated_years": paginated_years,
        }

        return TemplateResponse(request, "annual_summary/layout.html", data)


@login_required
def personal_annual_summary(request, year):
    """redirect simple URL to URL with username"""

    return redirect("annual-summary", request.user.localname, year)


@login_required
@require_POST
def summary_add_key(request):
    """add summary key"""

    year = request.POST["year"]
    user = request.user

    new_key = uuid4().hex

    if not user.summary_keys:
        user.summary_keys = {
            year: new_key,
        }
    else:
        user.summary_keys[year] = new_key

    user.save()

    response = redirect("annual-summary", user.localname, year)
    response["Location"] += f"?key={str(new_key)}"
    return response


@login_required
@require_POST
def summary_revoke_key(request):
    """revoke summary key"""

    year = request.POST["year"]
    user = request.user

    if user.summary_keys and year in user.summary_keys:
        user.summary_keys.pop(year)

    user.save()

    return redirect("annual-summary", user.localname, year)


def get_annual_summary_year():
    """return the latest available annual summary year or None"""

    today = date.today()
    if date(today.year, 12, FIRST_DAY) <= today <= date(today.year, 12, 31):
        return today.year

    if LAST_DAY > 0 and date(today.year, 1, 1) <= today <= date(
        today.year, 1, LAST_DAY
    ):
        return today.year - 1

    return None


def is_year_available(year):
    """return boolean"""

    today = date.today()
    year = int(year)
    if year < today.year:
        return True
    if year == today.year and today >= date(today.year, 12, FIRST_DAY):
        return True

    return False


def get_read_book_ids_in_year(user, year):
    """return an ordered QuerySet of the read book ids"""

    read_shelf = get_object_or_404(user.shelf_set, identifier="read")
    read_book_ids_in_year = (
        models.ShelfBook.objects.filter(shelf=read_shelf)
        .filter(user=user)
        .filter(shelved_date__year=year)
        .order_by("shelved_date", "created_date", "updated_date")
        .values_list("book", flat=True)
    )
    return read_book_ids_in_year


def get_books_from_shelfbooks(books_ids):
    """return an ordered QuerySet of books from a list"""

    ordered = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(books_ids)])
    books = models.Edition.objects.filter(id__in=books_ids).order_by(ordered)

    return books
