"""test file management"""

from datetime import datetime, timedelta, timezone
from os import listdir
import pathlib
from unittest.mock import patch

from PIL import Image
import responses

from django.core.files.base import ContentFile
from django.test import TestCase

from bookwyrm.book_search import SearchResult
from bookwyrm.models import (
    Author,
    BookwyrmExportJob,
    BookwyrmImportJob,
    CleanUpUserExportFilesJob,
    Connector,
    Edition,
    SiteSettings,
    start_export_deletions,
    User,
    Work,
)
from bookwyrm.models.housekeeping import (
    FindMissingCoversJob,
    get_cover_from_identifiers,
    get_covers_with_incorrect_filepaths,
    run_missing_covers_job,
)
from bookwyrm.settings import DOMAIN
from bookwyrm.models.housekeeping import delete_user_export_file_task


class TestCleanUpExportFiles(TestCase):
    """export and import files should be deleted periodically"""

    def setUp(self):
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            self.user = User.objects.create_user(
                f"mouse@{DOMAIN}",
                "mouse@mouse.mouse",
                "mouseword",
                local=True,
                localname="mouse",
                name="hi",
                summary="a summary",
                bookwyrm_user=False,
            )

            expiry_date = datetime.now(timezone.utc) - timedelta(hours=2)
            self.job = CleanUpUserExportFilesJob.objects.create(
                user=self.user, expiry_date=expiry_date
            )

            SiteSettings.objects.create()

    def test_export_file_deleted(self, *_):
        """did the file actually get deleted?"""

        export_updated_date = datetime.now(timezone.utc) - timedelta(hours=3)
        export = BookwyrmExportJob.objects.create(
            user=self.user,
            export_data=ContentFile(b"..", name="zzz_testfile.tar.gz"),
            updated_date=export_updated_date,
            complete=True,
        )

        self.assertTrue(export.export_data.name)
        delete_user_export_file_task(job_id=self.job.id, export_id=export.id)
        export.refresh_from_db()
        self.assertFalse(export.export_data.name)

    def test_import_file_deleted(self, *_):
        """did the file actually get deleted?"""

        updated_date = datetime.now(timezone.utc) - timedelta(hours=3)
        import_job = BookwyrmImportJob.objects.create(
            user=self.user,
            archive_file=ContentFile(b"xx", name="zzz_testfile.tar.gz"),
            updated_date=updated_date,
            complete=True,
            required=[],
        )

        self.assertTrue(import_job.archive_file.name)
        delete_user_export_file_task(job_id=self.job.id, import_id=import_job.id)
        import_job.refresh_from_db()
        self.assertFalse(import_job.archive_file.name)

    def test_renamed_file_deleted(self, *_):
        """files with duplicate names get renamed like filename.tar7x9e.gz"""

        export_updated_date = datetime.now(timezone.utc) - timedelta(hours=3)
        export = BookwyrmExportJob.objects.create(
            user=self.user,
            export_data=ContentFile(b"...", name="zzz_testfile.tar.gz"),
            updated_date=export_updated_date,
            complete=True,
        )

        self.assertTrue(export.export_data)
        export.refresh_from_db()
        delete_user_export_file_task(job_id=self.job.id, export_id=export.id)
        export.refresh_from_db()
        self.assertFalse(export.export_data.name)

    def test_start_export_deletions(self, *_):
        """does start_export_deletions actually start a job?"""

        self.assertEqual(CleanUpUserExportFilesJob.objects.count(), 1)

        start_export_deletions(user=self.user.id)

        self.assertEqual(CleanUpUserExportFilesJob.objects.count(), 2)
        self.assertNotEqual(CleanUpUserExportFilesJob.objects.last().status, "pending")

    def tearDown(self):
        """clean up any files"""

        for filename in listdir("exports"):
            if "zzz_testfile.tar" in filename:
                pathlib.Path(f"exports/{filename}").unlink(missing_ok=True)


class Covers(TestCase):
    """check our covers utils"""

    @classmethod
    def setUpTestData(cls):
        """set up the data we need"""

        cls.user = User.objects.create_user(
            f"mouse@{DOMAIN}",
            "mouse@mouse.mouse",
            local=True,
            localname="mouse",
        )

        Connector.objects.create(
            identifier="example.com",
            connector_file="bookwyrm_connector",
            base_url="https://example.com",
            books_url="https://example.com",
            covers_url="https://example.com/images/covers",
            search_url="https://example.com/search?q=",
            active=True,
        )

        cls.connector = Connector("example.com")

        cls.work = Work.objects.create(
            title="Entangled Life", remote_id="https://example.com/book/1"
        )

        cls.first_edition = Edition.objects.create(
            title="Entangled Life", parent_work=cls.work, isbn_13="9780525510321"
        )

        cls.second_edition = Edition.objects.create(
            title="Entangled Life", parent_work=cls.work, isbn_13="9781784708276"
        )

        cls.author = Author.objects.create(name="Merlin Sheldrake")
        cls.first_edition.authors.add(cls.author)
        cls.second_edition.authors.add(cls.author)

        cls.result = SearchResult(
            key=cls.first_edition.remote_id,
            title=cls.first_edition.title,
            author=cls.author,
            confidence=1,
            connector=cls.connector,
        )

        cls.query_response = [{"connector": cls.connector, "results": [cls.result]}]

        cls.book_json = {
            "title": "Entangled Life",
            "isbn_13": "9780525510321",
            "cover": {"url": "https://example.com/images/covers/test_image.jpeg"},
        }

    def setUp(self):
        """image file for testing"""

        image = Image.new("RGB", (1, 1))
        image.save("test_image.jpg", xmp=b"...")

    def test_get_cover_from_identifer(self):
        """Get missing cover from remote source"""

        with open("test_image.jpg", "r+b") as f:
            self.second_edition.cover.save("test_image.jpeg", f)
            responses.add(
                responses.GET,
                "https://example.com/images/covers/test_image.jpeg",
                f,
            )

            self.assertEqual(self.first_edition.cover, None)

            with (
                patch(
                    "bookwyrm.models.housekeeping.search",
                    return_value=self.query_response,
                ),
                patch(
                    "bookwyrm.models.housekeeping.get_data", return_value=self.book_json
                ),
                patch(
                    "bookwyrm.models.housekeeping.set_cover_from_url",
                    return_value=["test_image.jpeg", f],
                ),
            ):
                get_cover_from_identifiers(self.first_edition)

            self.assertNotEqual(self.first_edition.cover, None)

    def test_get_covers_with_incorrect_filepaths(self):
        """does get_coverless_books return books with wrong cover filepaths?"""

        with open("test_image.jpg", "r+b") as f:
            self.second_edition.cover.save("test_image2.jpeg", f)

        self.assertNotEqual(self.second_edition.cover, None)

        self.second_edition.cover.name = "wrong/name.png"
        self.second_edition.save(update_fields=["cover"])

        cl = get_covers_with_incorrect_filepaths()

        self.assertTrue(self.second_edition in cl)

    def test_trigger_job_for_missing_covers(self):
        """create a job and add coverless editions to it"""

        self.assertEqual(FindMissingCoversJob.objects.count(), 0)

        with patch("bookwyrm.models.housekeeping.get_missing_cover_task.delay"):
            run_missing_covers_job(user_id=self.user.id)

        self.assertEqual(FindMissingCoversJob.objects.count(), 1)
        job = FindMissingCoversJob.objects.first()
        self.assertEqual(job.editions.count(), 2)

    def test_trigger_job_for_wrong_filepath(self):
        """create a job and add editions with incorrect cover paths to it"""

        with open("test_image.jpg", "r+b") as f:
            self.second_edition.cover.save("test_image3.jpeg", f)
            self.second_edition.cover.name = "wrong/name.png"
            self.second_edition.save(update_fields=["cover"])

            self.assertEqual(FindMissingCoversJob.objects.count(), 0)

            with patch("bookwyrm.models.housekeeping.get_missing_cover_task.delay"):
                run_missing_covers_job(user_id=self.user.id, type="wrong_path")

            self.assertEqual(FindMissingCoversJob.objects.count(), 1)
            edition = FindMissingCoversJob.objects.first().editions.first()
            self.assertEqual(edition.isbn_13, "9781784708276")

    def tearDown(self):
        """clean up files"""

        for filename in [
            "test_image.jpg",
            "covers/test_image.jpeg",
            "covers/test_image2.jpeg",
            "covers/test_image3.jpeg",
        ]:
            pathlib.Path(filename).unlink(missing_ok=True)
