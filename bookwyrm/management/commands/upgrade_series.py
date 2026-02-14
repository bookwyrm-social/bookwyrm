"""fix legacy series"""

from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import Subquery, Q
from django.db.models.functions import Length
from bookwyrm import activitypub
from bookwyrm.models import Book, Edition, Series, SeriesBook, User


def upgrade_series_data():
    """turn strings into things"""

    series_count = Series.objects.count()
    seriesbook_count = SeriesBook.objects.count()

    for book in Edition.objects.exclude(series=None):
        user = activitypub.get_representative()
        vector = SearchVector("name", weight="A") + SearchVector(
            "alternative_names", weight="B"
        )
        possible_series = (
            Series.objects.annotate(search=vector)
            .annotate(rank=SearchRank(vector, book.series, normalization=32))
            .filter(rank__gt=0.19)
            .order_by("-rank")
        )

        if possible_series.exists():
            books = Edition.objects.filter(
                authors__in=Subquery(book.authors.values("pk"))
            ).values(
                "parent_work__pk"
            )  # the parent work is the book attached to the series

            same_author_sb = SeriesBook.objects.filter(book__in=books).filter(
                series__in=Subquery(possible_series.values("pk"))
            )  # there is a possible series with a seriesbook by a matching author

            match = same_author_sb.filter(
                Q(series__name__iexact=book.series)
                | Q(series__alternative_names__icontains=book.series)
            )  # it's the same series

            if match:
                series = match.first().series

            else:
                # there might be a matching series but we don't know
                # leave it for a user to work out manually
                continue
        else:
            series = Series.objects.create(user=user, name=book.series)

        if not SeriesBook.objects.filter(
            book=book.parent_work, series=series
        ).exists():  # the series might match because the parent work is already attached to the series. Don't try to duplicate it.
            SeriesBook.objects.create(
                user=user,
                series=series,
                book=book.parent_work,
                series_number=book.series_number,
            )

        book.series = None
        book.series_number = None
        book.save(broadcast=False)

    # print how many things we created
    new_series_count = Series.objects.count()
    new_seriesbook_count = SeriesBook.objects.count()
    net_series = new_series_count - series_count
    net_books = new_seriesbook_count - seriesbook_count

    print("-------")
    print(f"Created {net_series} new Series and {net_books} new SeriesBooks")


class Command(BaseCommand):
    """Turn legacy series data into Series and SeriesBook objects"""

    help = "Turn legacy series data into Series and SeriesBook objects"

    def handle(self, *args, **options):
        """run data migration"""
        upgrade_series_data()
