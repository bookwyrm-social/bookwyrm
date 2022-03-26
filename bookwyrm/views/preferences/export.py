""" Let users export their book data """
import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.template.response import TemplateResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET

from bookwyrm import models

# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class Export(View):
    """Let users export data"""

    def get(self, request):
        """Request csv file"""
        return TemplateResponse(request, "preferences/export.html")


@login_required
@require_GET
def export_user_book_data(request):
    """Streaming the csv file of a user's book data"""
    data = (
        models.Edition.viewer_aware_objects(request.user)
        .filter(
            Q(shelves__user=request.user)
            | Q(readthrough__user=request.user)
            | Q(review__user=request.user)
            | Q(comment__user=request.user)
            | Q(quotation__user=request.user)
        )
        .distinct()
    )

    generator = csv_row_generator(data, request.user)

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    # for testing, if you want to see the results in the browser:
    # from django.http import JsonResponse
    # return JsonResponse(list(generator), safe=False)
    return StreamingHttpResponse(
        (writer.writerow(row) for row in generator),
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bookwyrm-export.csv"'},
    )


def csv_row_generator(books, user):
    """generate a csv entry for the user's book"""
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
    yield fields
    for book in books:
        # I think this is more efficient than doing a subquery in the view? but idk
        review_rating = (
            models.Review.objects.filter(user=user, book=book, rating__isnull=False)
            .order_by("-published_date")
            .first()
        )

        book.rating = review_rating.rating if review_rating else None

        review = (
            models.Review.objects.filter(user=user, book=book, content__isnull=False)
            .order_by("-published_date")
            .first()
        )
        if review:
            book.review_name = review.name
            book.review_cw = review.content_warning
            book.review_content = review.raw_content
        yield [getattr(book, field, "") or "" for field in fields]


class Echo:
    """An object that implements just the write method of the file-like
    interface. (https://docs.djangoproject.com/en/3.2/howto/outputting-csv/)
    """

    # pylint: disable=no-self-use
    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value
