"""Import data from Bookwyrm export files"""
from bookwyrm import settings
from bookwyrm.models.bookwyrm_import_job import BookwyrmImportJob


class BookwyrmImporter:
    """Import a Bookwyrm User export JSON file.
    This is kind of a combination of an importer and a connector.
    """

    def process_import(self, user, archive_file, settings):
        """import user data from a Bookwyrm export file"""

        required = [k for k in settings if settings.get(k) == "on"]

        job = BookwyrmImportJob.objects.create(
            user=user, archive_file=archive_file, required=required
        )
        return job
