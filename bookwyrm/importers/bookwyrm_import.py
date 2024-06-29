"""Import data from Bookwyrm export files"""
from django.http import QueryDict

from bookwyrm.models import User
from bookwyrm.models.bookwyrm_import_job import BookwyrmImportJob


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
