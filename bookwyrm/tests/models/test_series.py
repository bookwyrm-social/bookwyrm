"""testing series models"""

from django.test import TestCase

from bookwyrm import models, settings


class TestSeriesModel(TestCase):
    """testing series"""

    @classmethod
    def setUpTestData(cls):
        """reusable data"""

        cls.instance_user = models.User.objects.create_user(
            "instance@local.com",
            local=True,
            localname=settings.INSTANCE_ACTOR_USERNAME,
            remote_id="https://example.com/users/instance_actor",
        )

        cls.work = models.Work.objects.create(title="Test Book")
        cls.edition = models.Edition.objects.create(
            title="Test Book", parent_work=cls.work
        )
        cls.series = models.Series.objects.create(
            user=cls.instance_user, name="Test series"
        )

    def test_seriesbook(self):
        """making a seriesbook"""

        self.assertEqual(models.SeriesBook.objects.count(), 0)
        models.SeriesBook.objects.create(
            series=self.series, book=self.work, user=self.instance_user
        )
        self.assertEqual(models.SeriesBook.objects.count(), 1)

    def test_seriesbook_fields(self):
        """do reverse fields work for seriesbook?"""

        self.assertEqual(models.SeriesBook.objects.count(), 0)
        seriesbook = models.SeriesBook.objects.create(
            series=self.series, book=self.work, user=self.instance_user
        )

        self.assertEqual(models.SeriesBook.objects.count(), 1)
        self.assertEqual(self.work.seriesbooks.first(), seriesbook)
        self.assertEqual(self.work.book_series()[0], self.series)
        self.assertEqual(self.series.seriesbooks.first(), seriesbook)

    def test_natural_sort_key(self):
        cases = {
            "2": (2.0, ""),
            "0": (0.0, ""),
            "0a": (0.0, "a"),
            "10": (10.0, ""),
            "4.5": (4.5, ""),
            "01": (1.0, ""),
            "007": (7.0, ""),
            "2-beta": (2.0, "-beta"),
            "1.5-rc": (1.5, "-rc"),
            "12abc34": (12.0, "abc34"),
            # values without a leading number sort last
            "Prequel": (float("inf"), "Prequel"),
            "abc123": (float("inf"), "abc123"),
            "Book 2": (float("inf"), "Book 2"),
            " 2": (float("inf"), " 2"),
            "v2": (float("inf"), "v2"),
            None: (float("inf"), ""),
            "": (float("inf"), ""),
        }
        for number, expected in cases.items():
            with self.subTest(series_number=number):
                seriesbook = models.SeriesBook(series_number=number)
                self.assertEqual(seriesbook.natural_sort_key, expected)
