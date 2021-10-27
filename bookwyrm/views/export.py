""" Let users export their book data """
import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET

from bookwyrm import models


class Echo:
    """An object that implements just the write method of the file-like
    interface. (https://docs.djangoproject.com/en/3.2/howto/outputting-csv/)
    """

    # pylint: disable=no-self-use
    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


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

    generator = csv_row_generator(data)

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    return StreamingHttpResponse(
        (writer.writerow(row) for row in generator),
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bookwyrm-export.csv"'},
    )


def csv_row_generator(books):
    """generate a csv entry for the user's book"""
    deduplication_fields = [  # pylint: disable=protected-access
        f.name
        for f in models.Edition._meta.get_fields()
        if getattr(f, "deduplication_field", False)
    ]
    fields = ["title"] + deduplication_fields
    yield fields
    for book in books:
        yield [getattr(book, field, "") or "" for field in fields]
