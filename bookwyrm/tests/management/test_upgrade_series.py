"""test the series upgrade command works"""

from django.test import TestCase
from django.db.models import Subquery, Count

from bookwyrm.management.commands import add_libris_connector
from bookwyrm import models
from bookwyrm.management.commands.upgrade_series import upgrade_series_data


class UpgradeSeries(TestCase):
    """ "test upgrade series"""

    @classmethod
    def setUpTestData(cls):
        # create a bunch of authors
        cls.author_one = models.Author.objects.create(name="Alice Alicedottir")
        cls.author_two = models.Author.objects.create(name="Bob Bobson")
        cls.author_three = models.Author.objects.create(name="Sam Xu")

        # create a bunch of works
        cls.work_one = models.Work.objects.create(title="First test book")
        cls.work_two = models.Work.objects.create(title="Another tome")
        cls.work_three = models.Work.objects.create(
            title="Thrice we create reading material"
        )

        # create a bunch of editions
        cls.edition_one = models.Edition.objects.create(
            title="First test book", parent_work=cls.work_one, series="First series"
        )
        cls.edition_one.authors.add(cls.author_one)

        cls.edition_two = models.Edition.objects.create(
            title="First test book",
            parent_work=cls.work_one,
            oclc_number="1234",
            series="First series",
        )
        cls.edition_two.authors.add(cls.author_one)

        cls.edition_three = models.Edition.objects.create(
            title="Another tome",
            parent_work=cls.work_two,
            series="A series by any other name",
            series_number="1",
        )
        cls.edition_three.authors.add(cls.author_one)
        cls.edition_three.authors.add(cls.author_two)

        cls.edition_four = models.Edition.objects.create(
            title="Another tome",
            parent_work=cls.work_two,
            oclc_number="5678",
            series="SERIES By Other Name",
        )  # should be retained for checking
        cls.edition_four.authors.add(cls.author_one)
        cls.edition_four.authors.add(cls.author_three)

        cls.edition_five = models.Edition.objects.create(
            title="Thrice we create reading material",
            parent_work=cls.work_three,
            series="A series by any other name",
            series_number="second book",
        )  # different parent work, same series, series_number is non-int
        cls.edition_five.authors.add(cls.author_three)

        cls.edition_six = models.Edition.objects.create(
            title="Thrice we create reading material",
            parent_work=cls.work_three,
            series="A great set of books to test",
        )  # standalone
        cls.edition_six.authors.add(cls.author_three)

    def test_upgrade_series_data(self):
        """ "test upgrade series command"""

        upgrade_series_data()

        """
        3 series
        4 seriesbooks:
            First test book / first series
            Another tome / a series by any other name
            Thrice we create / a series by any other name
            Thrice we create / a great set of books
        """
        self.assertEqual(models.Series.objects.count(), 3)
        self.assertEqual(models.SeriesBook.objects.count(), 4)

    def test_ugrade_series_data_correct_series(self):
        """Edition 4 retains "series" value and parent_work has no seriesbook"""

        upgrade_series_data()

        self.assertEqual(models.Edition.objects.filter(series__isnull=False).count(), 1)
        self.assertEqual(self.edition_four.seriesbooks.count(), 0)

    def test_ugrade_series_data_correct_series_numbers(self):
        """are series numbers applied correctly"""

        upgrade_series_data()
        # two with series_number
        self.assertEqual(
            models.SeriesBook.objects.filter(series_number__isnull=False).count(), 2
        )

    def test_ugrade_series_data_attaches_correct_authors(self):
        """are authors applied correctly"""

        upgrade_series_data()
        # cls.author_one attached to 2 series
        b = models.Edition.objects.filter(authors__id=self.author_one.id)
        unique = (
            models.SeriesBook.objects.filter(book__in=Subquery(b.values("parent_work")))
            .order_by("series")
            .distinct("series")
            .count()
        )
        self.assertEqual(unique, 2)

        # # cls.author_two attached to 1 series
        b_two = models.Edition.objects.filter(authors__id=self.author_two.id)
        unique_two = (
            models.SeriesBook.objects.filter(
                book__in=Subquery(b_two.values("parent_work"))
            )
            .order_by("series")
            .distinct("series")
            .count()
        )
        self.assertEqual(unique_two, 1)

        # # cls.author_three attached to 2 series
        b_three = models.Edition.objects.filter(authors__id=self.author_three.id)
        unique_three = (
            models.SeriesBook.objects.filter(
                book__in=Subquery(b_three.values("parent_work"))
            )
            .order_by("series")
            .distinct("series")
            .count()
        )
        self.assertEqual(unique_three, 2)

    def test_ugrade_series_data_ignores_orphan_editions(self):
        """do we successfully not choke on editions that match but don't have parents?"""

        book_seven = models.Edition.objects.create(
            title="Yet another tome, OMG so many",
            series="A series by any other name",
            series_number="7",
        )
        book_seven.authors.add(self.author_one)

        upgrade_series_data()

        # if we don't get any errors here, it works ;)
