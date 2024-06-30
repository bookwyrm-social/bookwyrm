"""Import data from Bookwyrm export files"""
from typing import Any
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


class BookwyrmBooksImporter(Importer):
    """
    Handle reading a csv from BookWyrm.
    Goodreads is the default importer, we basically just use the same structure
    But BookWyrm has a shelf.id (shelf) and a shelf.name (shelf_name)
    """

    service = "BookWyrm"

    def __init__(self, *args: Any, **kwargs: Any):
        self.row_mappings_guesses.append(("shelf_name", ["shelf_name"]))
        super().__init__(*args, **kwargs)
