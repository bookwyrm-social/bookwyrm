from django.db.models import Case, When
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import models


class AnnualSummary(View):
    """display a summary of the year"""

    def get(self, request, year):
        """get response"""

        user = request.user
        read_shelf = get_object_or_404(user.shelf_set, identifier="read")
        read_shelf_books_in_year = (
            models.ShelfBook.objects.filter(shelf=read_shelf)
            .filter(user=user)
            .filter(shelved_date__year=year)
            .order_by("shelved_date", "created_date", "updated_date")
        )
        read_book_ids_in_year = [i.book.id for i in read_shelf_books_in_year]
        preserved = Case(
            *[When(pk=pk, then=pos) for pos, pk in enumerate(read_book_ids_in_year)]
        )
        read_books_in_year = models.Edition.objects.filter(
            id__in=read_book_ids_in_year
        ).order_by(preserved)

        """pages stats queries"""
        read_books_with_pages = read_books_in_year.filter(pages__gte=0).order_by(
            "pages"
        )
        pages_list = [p.pages for p in read_books_with_pages]

        pages_total = 0
        pages_average = 0
        book_pages_lowest = 0
        book_pages_highest = 0
        if len(pages_list) > 0:
            pages_total = sum(pages_list)
            pages_average = round(sum(pages_list) / len(pages_list))
            book_pages_lowest = read_books_with_pages.first()
            book_pages_highest = read_books_with_pages.last()

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

        rating_average = 0
        if len(ratings) > 0:
            ratings_list = [review.rating for review in ratings]
            rating_average = round(sum(ratings_list) / len(ratings_list), 2)

        data = {
            "year": year,
            "books_total": len(read_books_in_year),
            "books": read_books_in_year,
            "pages_total": pages_total,
            "pages_average": pages_average,
            "book_pages_lowest": book_pages_lowest,
            "book_pages_highest": book_pages_highest,
            "no_page_number": no_page_list,
            "ratings_total": len(ratings),
            "rating_average": rating_average,
            "book_rating_highest": ratings.order_by("-rating").first(),
            "best_ratings_books_ids": best_ratings_books_ids,
        }

        return TemplateResponse(request, "annual_summary/layout.html", data)
