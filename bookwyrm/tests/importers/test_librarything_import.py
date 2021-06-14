""" testing import """
import csv
import pathlib
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.importers import LibrarythingImporter
from bookwyrm.importers.importer import import_data, handle_imported_book
from bookwyrm.settings import DOMAIN


class LibrarythingImport(TestCase):
    """importing from librarything tsv"""

    def setUp(self):
        """use a test tsv"""
        self.importer = LibrarythingImporter()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/librarything.tsv")

        # Librarything generates latin encoded exports...
        self.csv = open(datafile, "r", encoding=self.importer.encoding)
        self.user = models.User.objects.create_user(
            "mmai", "mmai@mmai.mmai", "password", local=True
        )

        models.Connector.objects.create(
            identifier=DOMAIN,
            name="Local",
            local=True,
            connector_file="self_connector",
            base_url="https://%s" % DOMAIN,
            books_url="https://%s/book" % DOMAIN,
            covers_url="https://%s/images/covers" % DOMAIN,
            search_url="https://%s/search?q=" % DOMAIN,
            priority=1,
        )
        work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )

    def test_create_job(self):
        """creates the import job entry and checks csv"""
        import_job = self.importer.create_job(self.user, self.csv, False, "public")
        self.assertEqual(import_job.user, self.user)
        self.assertEqual(import_job.include_reviews, False)
        self.assertEqual(import_job.privacy, "public")

        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(len(import_items), 3)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data["Book Id"], "5498194")
        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].data["Book Id"], "5015319")
        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].data["Book Id"], "5015399")

    def test_create_retry_job(self):
        """trying again with items that didn't import"""
        import_job = self.importer.create_job(self.user, self.csv, False, "unlisted")
        import_items = models.ImportItem.objects.filter(job=import_job).all()[:2]

        retry = self.importer.create_retry_job(self.user, import_job, import_items)
        self.assertNotEqual(import_job, retry)
        self.assertEqual(retry.user, self.user)
        self.assertEqual(retry.include_reviews, False)
        self.assertEqual(retry.privacy, "unlisted")

        retry_items = models.ImportItem.objects.filter(job=retry).all()
        self.assertEqual(len(retry_items), 2)
        self.assertEqual(retry_items[0].index, 0)
        self.assertEqual(import_items[0].data["Book Id"], "5498194")
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].data["Book Id"], "5015319")

    @responses.activate
    def test_import_data(self):
        """resolve entry"""
        import_job = self.importer.create_job(self.user, self.csv, False, "unlisted")
        book = models.Edition.objects.create(title="Test Book")

        with patch(
            "bookwyrm.models.import_job.ImportItem.get_book_from_isbn"
        ) as resolve:
            resolve.return_value = book
            with patch("bookwyrm.importers.importer.handle_imported_book"):
                import_data(self.importer.service, import_job.id)

        import_item = models.ImportItem.objects.get(job=import_job, index=0)
        self.assertEqual(import_item.book.id, book.id)

    def test_handle_imported_book(self):
        """librarything import added a book, this adds related connections"""
        shelf = self.user.shelf_set.filter(identifier="read").first()
        self.assertIsNone(shelf.books.first())

        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/librarything.tsv")
        csv_file = open(datafile, "r", encoding=self.importer.encoding)
        for index, entry in enumerate(
            list(csv.DictReader(csv_file, delimiter=self.importer.delimiter))
        ):
            entry = self.importer.parse_fields(entry)
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book
            )
            break

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            handle_imported_book(
                self.importer.service, self.user, import_item, False, "public"
            )

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

        readthrough = models.ReadThrough.objects.get(user=self.user)
        self.assertEqual(readthrough.book, self.book)
        # I can't remember how to create dates and I don't want to look it up.
        self.assertEqual(readthrough.start_date.year, 2007)
        self.assertEqual(readthrough.start_date.month, 4)
        self.assertEqual(readthrough.start_date.day, 16)
        self.assertEqual(readthrough.finish_date.year, 2007)
        self.assertEqual(readthrough.finish_date.month, 5)
        self.assertEqual(readthrough.finish_date.day, 8)

    def test_handle_imported_book_already_shelved(self):
        """librarything import added a book, this adds related connections"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            shelf = self.user.shelf_set.filter(identifier="to-read").first()
            models.ShelfBook.objects.create(shelf=shelf, user=self.user, book=self.book)

        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/librarything.tsv")
        csv_file = open(datafile, "r", encoding=self.importer.encoding)
        for index, entry in enumerate(
            list(csv.DictReader(csv_file, delimiter=self.importer.delimiter))
        ):
            entry = self.importer.parse_fields(entry)
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book
            )
            break

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            handle_imported_book(
                self.importer.service, self.user, import_item, False, "public"
            )

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
        self.assertIsNone(self.user.shelf_set.get(identifier="read").books.first())
        readthrough = models.ReadThrough.objects.get(user=self.user)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.start_date.year, 2007)
        self.assertEqual(readthrough.start_date.month, 4)
        self.assertEqual(readthrough.start_date.day, 16)
        self.assertEqual(readthrough.finish_date.year, 2007)
        self.assertEqual(readthrough.finish_date.month, 5)
        self.assertEqual(readthrough.finish_date.day, 8)

    def test_handle_import_twice(self):
        """re-importing books"""
        shelf = self.user.shelf_set.filter(identifier="read").first()
        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/librarything.tsv")
        csv_file = open(datafile, "r", encoding=self.importer.encoding)
        for index, entry in enumerate(
            list(csv.DictReader(csv_file, delimiter=self.importer.delimiter))
        ):
            entry = self.importer.parse_fields(entry)
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book
            )
            break

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            handle_imported_book(
                self.importer.service, self.user, import_item, False, "public"
            )
            handle_imported_book(
                self.importer.service, self.user, import_item, False, "public"
            )

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

        readthrough = models.ReadThrough.objects.get(user=self.user)
        self.assertEqual(readthrough.book, self.book)
        # I can't remember how to create dates and I don't want to look it up.
        self.assertEqual(readthrough.start_date.year, 2007)
        self.assertEqual(readthrough.start_date.month, 4)
        self.assertEqual(readthrough.start_date.day, 16)
        self.assertEqual(readthrough.finish_date.year, 2007)
        self.assertEqual(readthrough.finish_date.month, 5)
        self.assertEqual(readthrough.finish_date.day, 8)

    @patch("bookwyrm.activitystreams.ActivityStream.add_status")
    def test_handle_imported_book_review(self, _):
        """librarything review import"""
        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/librarything.tsv")
        csv_file = open(datafile, "r", encoding=self.importer.encoding)
        entry = list(csv.DictReader(csv_file, delimiter=self.importer.delimiter))[0]
        entry = self.importer.parse_fields(entry)
        import_item = models.ImportItem.objects.create(
            job_id=import_job.id, index=0, data=entry, book=self.book
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            handle_imported_book(
                self.importer.service, self.user, import_item, True, "unlisted"
            )
        review = models.Review.objects.get(book=self.book, user=self.user)
        self.assertEqual(review.content, "chef d'oeuvre")
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.published_date.year, 2007)
        self.assertEqual(review.published_date.month, 5)
        self.assertEqual(review.published_date.day, 8)
        self.assertEqual(review.privacy, "unlisted")

    def test_handle_imported_book_reviews_disabled(self):
        """librarything review import"""
        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/librarything.tsv")
        csv_file = open(datafile, "r", encoding=self.importer.encoding)
        entry = list(csv.DictReader(csv_file, delimiter=self.importer.delimiter))[2]
        entry = self.importer.parse_fields(entry)
        import_item = models.ImportItem.objects.create(
            job_id=import_job.id, index=0, data=entry, book=self.book
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            handle_imported_book(
                self.importer.service, self.user, import_item, False, "unlisted"
            )
        self.assertFalse(
            models.Review.objects.filter(book=self.book, user=self.user).exists()
        )
