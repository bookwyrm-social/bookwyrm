""" testing import """
from collections import namedtuple
import csv
import pathlib
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.importers import IsbnImporter
from bookwyrm.importers.importer import import_data, handle_imported_book
from bookwyrm.settings import DOMAIN


class IsbnImport(TestCase):
    """importing from goodreads csv"""

    def setUp(self):
        """use a test csv"""
        self.importer = IsbnImporter()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/isbn.txt")
        self.csv = open(datafile, "r", encoding=self.importer.encoding)
        with patch("bookwyrm.preview_images.generate_user_preview_image_task.delay"):
            self.user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True
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
        with patch("bookwyrm.preview_images.generate_edition_preview_image_task.delay"):
            work = models.Work.objects.create(title="Test Work")
            self.book = models.Edition.objects.create(
                title="Example Edition",
                remote_id="https://example.com/book/1",
                parent_work=work,
            )

    def test_create_job(self):
        """creates the import job entry and checks text file"""
        import_job = self.importer.create_job(
            self.user,
            self.csv,
            False,
            "public",
            file_type="txt",
            default_shelf="to-read",
        )
        self.assertEqual(import_job.user, self.user)
        self.assertEqual(import_job.include_reviews, False)
        self.assertEqual(import_job.privacy, "public")

        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(len(import_items), 2)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data["ISBN13"], "9781250313195")
        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].data["ISBN13"], "9780062445315")

    def test_create_retry_job(self):
        """trying again with items that didn't import"""
        import_job = self.importer.create_job(
            self.user,
            self.csv,
            False,
            "unlisted",
            file_type="txt",
            default_shelf="to-read",
        )
        import_items = models.ImportItem.objects.filter(job=import_job).all()[:1]

        retry = self.importer.create_retry_job(self.user, import_job, import_items)
        self.assertNotEqual(import_job, retry)
        self.assertEqual(retry.user, self.user)
        self.assertEqual(retry.include_reviews, False)
        self.assertEqual(retry.privacy, "unlisted")

        retry_items = models.ImportItem.objects.filter(job=retry).all()
        self.assertEqual(len(retry_items), 1)
        self.assertEqual(retry_items[0].index, 0)
        self.assertEqual(retry_items[0].data["ISBN13"], "9781250313195")

    @responses.activate
    def test_import_data(self):
        """resolve entry"""
        import_job = self.importer.create_job(
            self.user,
            self.csv,
            False,
            "unlisted",
            file_type="txt",
            default_shelf="to-read",
        )
        with patch("bookwyrm.preview_images.generate_edition_preview_image_task.delay"):
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
        """ISBN text import added a book, this adds related connections"""
        shelf = self.user.shelf_set.filter(identifier="read").first()
        self.assertIsNone(shelf.books.first())

        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/isbn.txt")
        csv_file = open(datafile, "r")
        for index, entry in enumerate(csv_file.read().splitlines()):
            entry = self.importer.parse_fields(entry, default_shelf="read")
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book
            )
            break

        with patch("bookwyrm.preview_images.generate_edition_preview_image_task.delay"):
            with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
                handle_imported_book(
                    self.importer.service, self.user, import_item, False, "public"
                )

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)

    def test_handle_imported_book_already_shelved(self):
        """goodreads import added a book, this adds related connections"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            shelf = self.user.shelf_set.filter(identifier="to-read").first()
            models.ShelfBook.objects.create(shelf=shelf, user=self.user, book=self.book)

        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/isbn.txt")
        csv_file = open(datafile, "r")
        for index, entry in enumerate(csv_file.read().splitlines()):
            entry = self.importer.parse_fields(entry, default_shelf="read")
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

    def test_handle_import_twice(self):
        """re-importing books"""
        shelf = self.user.shelf_set.filter(identifier="read").first()
        import_job = models.ImportJob.objects.create(user=self.user)
        datafile = pathlib.Path(__file__).parent.joinpath("../data/isbn.txt")
        csv_file = open(datafile, "r")
        for index, entry in enumerate(csv_file.read().splitlines()):
            entry = self.importer.parse_fields(entry, default_shelf="read")
            import_item = models.ImportItem.objects.create(
                job_id=import_job.id, index=index, data=entry, book=self.book
            )
            break

        with patch("bookwyrm.preview_images.generate_edition_preview_image_task.delay"):
            with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
                handle_imported_book(
                    self.importer.service, self.user, import_item, False, "unlisted"
                )
                handle_imported_book(
                    self.importer.service, self.user, import_item, False, "unlisted"
                )

        shelf.refresh_from_db()
        self.assertEqual(shelf.books.first(), self.book)
