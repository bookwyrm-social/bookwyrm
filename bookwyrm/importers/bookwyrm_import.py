"""Import data from Bookwyrm export files"""
from django.http import QueryDict

from bookwyrm.models import User
from bookwyrm.models.bookwyrm_import_job import BookwyrmImportJob
from . import Importer


class BookwyrmImporter:
    """Import a Bookwyrm User export file.
    This is kind of a combination of an importer and a connector.
    """

    # pylint: disable=no-self-use
    def process_import(
        self, user: User, archive_file: bytes, settings: QueryDict
    ) -> BookwyrmImportJob:
        """import user data from a Bookwyrm export file"""

        required = [k for k in settings if settings.get(k) == "on"]

        job = BookwyrmImportJob.objects.create(
            user=user, archive_file=archive_file, required=required
        )

        return job

    def create_retry_job(
        self, user: User, original_job: BookwyrmImportJob
    ) -> BookwyrmImportJob:
        """retry items that didn't import"""

        job = BookwyrmImportJob.objects.create(
            user=user,
            archive_file=original_job.archive_file,
            required=original_job.required,
            retry=True,
        )

        return job


class BookwyrmBooksImporter(Importer):
    """
    Handle reading a csv from BookWyrm.
    Goodreads is the default importer, we basically just use the same structure
    But BookWyrm has additional attributes in the csv
    """

    service = "BookWyrm"
    row_mappings_guesses = Importer.row_mappings_guesses + [
        ("shelf_name", ["shelf_name"]),
        ("review_published", ["review_published"]),
    ]
