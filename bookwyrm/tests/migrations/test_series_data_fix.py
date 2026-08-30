"""test fix stringified series objects doesn't make it worse"""

from importlib import import_module
from django.apps import apps
from django.db import connection
from django.test import TestCase
from bookwyrm import models
from bookwyrm.settings import INSTANCE_ACTOR_USERNAME

fix_series = import_module("bookwyrm.migrations.0243_auto_20260730_0926").fix_series


class TestFixSeriesObjects(TestCase):
    """test fix stringified series objects doesn't make it worse"""

    @classmethod
    def setUpTestData(cls):
        cls.user = models.User.objects.create_user(
            "instance",
            "mouse@mouse.mouse",
            "mouseword",
            local=True,
            localname=INSTANCE_ACTOR_USERNAME,
        )

        cls.work = models.Work.objects.create(
            title="test title", series='[{"name": "test series"}]'
        )

        cls.edition = models.Edition.objects.create(
            title="test title", parent_work=cls.work, series="blah"
        )

        base_url = "https://bookwyrm.social"
        models.Connector.objects.create(
            identifier="bookwyrm.social",
            connector_file="bookwyrm_connector",
            base_url=base_url,
            books_url=f"{base_url}/book",
            covers_url=f"{base_url}/images/covers",
            search_url=f"{base_url}/search?q=",
            priority=2,
        )

    def test_work_series_is_cleared(self):
        """is the series attached to the work cleared?"""

        fix_series(apps, connection.schema_editor())
        self.work.refresh_from_db()
        self.assertEqual(self.work.series, None)

    def test_work_has_seriesbook(self):
        """is the series turned into a seriesbook?"""

        fix_series(apps, connection.schema_editor())
        self.assertEqual(models.SeriesBook.objects.count(), 1)
        self.assertEqual(models.SeriesBook.objects.first().series.name, "test series")

    def test_edition_series_is_cleared(self):
        """is the series attached to the edition cleared?"""

        fix_series(apps, connection.schema_editor())
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.series, None)

    def test_string_series_is_not_cleared(self):
        """is the standard series string retained?"""

        self.work.series = None
        self.work.save()
        self.work.refresh_from_db()

        self.assertEqual(self.edition.series, "blah")
        fix_series(apps, connection.schema_editor())
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.series, "blah")

    def test_edition_with_stringified_series(self):
        """the work has no series and edition has stringified json"""

        self.work.series = None
        self.work.save()
        self.edition.series = '[{"name": "blah blah"}]'
        self.edition.save()
        self.assertEqual(models.SeriesBook.objects.count(), 0)
        fix_series(apps, connection.schema_editor())
        self.edition.refresh_from_db()
        self.work.refresh_from_db()
        self.assertEqual(self.edition.series, None)
        self.assertEqual(self.work.series, None)
        self.assertEqual(models.SeriesBook.objects.count(), 1)
        self.assertEqual(models.Series.objects.first().name, "blah blah")

    def test_fix_does_not_duplicate_series(self):
        """don't create another copy of an existing series"""

        # set up
        author = models.Author.objects.create(name="Arthur Author")
        new_work = models.Work.objects.create(title="new work")
        series = models.Series.objects.create(user=self.user, name="test series")
        models.SeriesBook.objects.create(user=self.user, book=new_work, series=series)
        new_work.authors.add(author)
        self.work.authors.add(author)

        # test
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(models.SeriesBook.objects.count(), 1)
        fix_series(apps, connection.schema_editor())
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(models.SeriesBook.objects.count(), 2)

    def test_fix_does_not_duplicate_seriesbook(self):
        """don't create another copy of an existing seriesbook"""

        # set up
        author = models.Author.objects.create(name="Arthur Author")
        series = models.Series.objects.create(user=self.user, name="test series")
        models.SeriesBook.objects.create(user=self.user, book=self.work, series=series)
        self.work.authors.add(author)

        # test
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(models.SeriesBook.objects.count(), 1)
        fix_series(apps, connection.schema_editor())
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(models.SeriesBook.objects.count(), 1)

    def test_work_without_edition(self):
        """childless works should clear continue"""

        self.edition.parent_work = None
        self.edition.save()
        fix_series(apps, connection.schema_editor())
        self.work.refresh_from_db()
        self.assertEqual(self.work.series, None)
        self.assertEqual(models.SeriesBook.objects.count(), 0)

    def test_edition_without_work(self):
        """orphaned editions should simply clear the series entry"""

        self.edition.parent_work = None
        self.edition.series = '[{"name": "blah blah"}]'
        self.edition.save()
        fix_series(apps, connection.schema_editor())
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.series, None)
        self.assertEqual(models.SeriesBook.objects.count(), 0)

    def test_invalid_object(self):
        """stringified objects without series keys will skip"""

        self.work.series = '[{"title": "blah blah"}]'
        self.work.save()
        self.edition.series = "Test series [something]"
        self.edition.save()
        fix_series(apps, connection.schema_editor())
        self.edition.refresh_from_db()
        self.assertEqual(self.edition.series, "Test series [something]")
        self.work.refresh_from_db()
        self.assertEqual(self.work.series, '[{"title": "blah blah"}]')
        self.assertEqual(models.SeriesBook.objects.count(), 0)
