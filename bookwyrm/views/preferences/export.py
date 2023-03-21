""" Let users export their book data """
import csv
import io

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.views import View
from django.utils.decorators import method_decorator

from bookwyrm import models

# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class Export(View):
    """Let users export data"""

    def get(self, request):
        """Request csv file"""
        return TemplateResponse(request, "preferences/export.html")

    def post(self, request):
        """Download the csv file of a user's book data"""
        books = models.Edition.viewer_aware_objects(request.user)
        books_shelves = books.filter(Q(shelves__user=request.user)).distinct()
        books_readthrough = books.filter(Q(readthrough__user=request.user)).distinct()
        books_review = books.filter(Q(review__user=request.user)).distinct()
        books_comment = books.filter(Q(comment__user=request.user)).distinct()
        books_quotation = books.filter(Q(quotation__user=request.user)).distinct()

        books = set(
            list(books_shelves)
            + list(books_readthrough)
            + list(books_review)
            + list(books_comment)
            + list(books_quotation)
        )

        csv_string = io.StringIO()
        writer = csv.writer(csv_string)

        deduplication_fields = [
            f.name
            for f in models.Edition._meta.get_fields()  # pylint: disable=protected-access
            if getattr(f, "deduplication_field", False)
        ]
        fields = (
            ["title", "author_text"]
            + deduplication_fields
            + ["rating", "review_name", "review_cw", "review_content"]
        )
        writer.writerow(fields)

        for book in books:
            # I think this is more efficient than doing a subquery in the view? but idk
            review_rating = (
                models.Review.objects.filter(
                    user=request.user, book=book, rating__isnull=False
                )
                .order_by("-published_date")
                .first()
            )

            book.rating = review_rating.rating if review_rating else None

            review = (
                models.Review.objects.filter(
                    user=request.user, book=book, content__isnull=False
                )
                .order_by("-published_date")
                .first()
            )
            if review:
                book.review_name = review.name
                book.review_cw = review.content_warning
                book.review_content = review.raw_content
            writer.writerow([getattr(book, field, "") or "" for field in fields])

        return HttpResponse(
            csv_string.getvalue(),
            content_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="bookwyrm-export.csv"'
            },
        )
