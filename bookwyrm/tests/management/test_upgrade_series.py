"""test the series upgrade command works"""

from django.test import TestCase
from django.db.models import Subquery, Count

from bookwyrm.management.commands import add_libris_connector
from bookwyrm import models
from bookwyrm.management.commands.upgrade_series import upgrade_series_data


class UpgradeSeries(TestCase):
    """ "test upgrade series"""

    def test_upgrade_series_data(self):
        """ "test upgrade series command"""
        # create a bunch of authors
        author_one = models.Author.objects.create(name="Alice Alicedottir")
        author_two = models.Author.objects.create(name="Bob Bobson")
        author_three = models.Author.objects.create(name="Sam Xu")

        # create a bunch of works
        work_one = models.Work.objects.create(title="First test book")
        work_two = models.Work.objects.create(title="Another tome")
        work_three = models.Work.objects.create(
            title="Thrice we create reading material"
        )

        # create a bunch of editions
        edition_one = models.Edition.objects.create(
            title="First test book", parent_work=work_one, series="First series"
        )
        edition_one.authors.add(author_one)

        edition_two = models.Edition.objects.create(
            title="First test book",
            parent_work=work_one,
            oclc_number="1234",
            series="First series",
        )
        edition_two.authors.add(author_one)

        edition_three = models.Edition.objects.create(
            title="Another tome",
            parent_work=work_two,
            series="A series by any other name",
            series_number="1",
        )
        edition_three.authors.add(author_one)
        edition_three.authors.add(author_two)

        edition_four = models.Edition.objects.create(
            title="Another tome",
            parent_work=work_two,
            oclc_number="5678",
            series="SERIES By Other Name",
        )  # should be retained for checking
        edition_four.authors.add(author_one)
        edition_four.authors.add(author_three)

        edition_five = models.Edition.objects.create(
            title="Thrice we create reading material",
            parent_work=work_three,
            series="A series by any other name",
            series_number="second book",
        )  # different parent work, same series, series_number is non-int
        edition_five.authors.add(author_three)

        edition_six = models.Edition.objects.create(
            title="Thrice we create reading material",
            parent_work=work_three,
            series="A great set of books to test",
        )  # standalone
        edition_six.authors.add(author_three)

        upgrade_series_data()

        # 3 series
        self.assertEqual(models.Series.objects.count(), 3)

        """
        4 seriesbooks
        First test book / first series
        Another tome / a series by any other name
        Thrice we create / a series by any other name
        Thrice we create / a great set of books
        """
        self.assertEqual(models.SeriesBook.objects.count(), 4)

        # Edition 4 retains "series" value and parent_work has no seriesbook
        self.assertEqual(models.Edition.objects.filter(series__isnull=False).count(), 1)
        self.assertEqual(edition_four.seriesbooks.count(), 0)

        # two with series_number
        self.assertEqual(
            models.SeriesBook.objects.filter(series_number__isnull=False).count(), 2
        )

        # author_one attached to 2 series
        b = models.Edition.objects.filter(authors__id=author_one.id)
        unique = (
            models.SeriesBook.objects.filter(book__in=Subquery(b.values("parent_work")))
            .order_by("series")
            .distinct("series")
            .count()
        )
        self.assertEqual(unique, 2)

        # # author_two attached to 1 series
        b_two = models.Edition.objects.filter(authors__id=author_two.id)
        unique_two = (
            models.SeriesBook.objects.filter(
                book__in=Subquery(b_two.values("parent_work"))
            )
            .order_by("series")
            .distinct("series")
            .count()
        )
        self.assertEqual(unique_two, 1)

        # # author_three attached to 2 series
        b_three = models.Edition.objects.filter(authors__id=author_three.id)
        unique_three = (
            models.SeriesBook.objects.filter(
                book__in=Subquery(b_three.values("parent_work"))
            )
            .order_by("series")
            .distinct("series")
            .count()
        )
        self.assertEqual(unique_three, 2)
