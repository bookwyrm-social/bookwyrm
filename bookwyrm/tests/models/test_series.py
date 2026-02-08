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
        cls.series = models.Series.objects.create(name="Test series")

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
