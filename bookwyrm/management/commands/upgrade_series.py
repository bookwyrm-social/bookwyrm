"""fix legacy series"""

from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models.functions import Length
from bookwyrm import activitypub
from bookwyrm.models import Book, Edition, Series, SeriesBook, User


def upgrade_series_data():
    """turn strings into things"""

    user = activitypub.get_representative()
    series_count = Series.objects.count()
    seriesbook_count = SeriesBook.objects.count()

    for book in (
        Edition.objects.filter(parent_work__seriesbooks=None).exclude(series=None).all()
    ):

        vector = SearchVector("name", weight="A") + SearchVector(
            "alternative_names", weight="B"
        )
        possible_series = (
            Series.objects.annotate(search=vector)
            .annotate(rank=SearchRank(vector, book.series, normalization=32))
            .filter(rank__gt=0.19)
            .order_by("-rank")[:5]
        )

        if possible_series.exists():

            books = Book.objects.filter(authors__in=Subquery(book.authors.values("pk")))

            if same_author_sb := SeriesBook.objects.filter(book__in=books).filter(
                series__in=Subquery(possible_series.values("pk"))
            ):
                # there is a series with a seriesbook by a matching author
                # let's feel lucky
                series = same_author_sb.first().series

            else:
                # there might be a matching series but we don't know
                # leave it for a user to work out manually
                continue
        else:
            series = Series.objects.create(name=book.series, user=user)

        SeriesBook.objects.create(
            series=series,
            book=book.parent_work,
            series_number=book.series_number,
            user=user,
        )

        book.series = None
        book.series_number = None

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

    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run data migration"""
        upgrade_series_data()
