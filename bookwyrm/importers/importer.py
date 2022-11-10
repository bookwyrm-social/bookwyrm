""" handle reading a csv from an external service, defaults are from Goodreads """
import csv
from django.utils import timezone
from bookwyrm.models import ImportJob, ImportItem


class Importer:
    """Generic class for csv data import from an outside service"""

    service = "Import"
    delimiter = ","
    encoding = "UTF-8"

    # these are from Goodreads
    row_mappings_guesses = [
        ("id", ["id", "book id"]),
        ("title", ["title"]),
        ("authors", ["author", "authors", "primary author"]),
        ("isbn_10", ["isbn10", "isbn"]),
        ("isbn_13", ["isbn13", "isbn", "isbns"]),
        ("shelf", ["shelf", "exclusive shelf", "read status", "bookshelf"]),
        ("review_name", ["review name"]),
        ("review_body", ["my review", "review"]),
        ("rating", ["my rating", "rating", "star rating"]),
        ("date_added", ["date added", "entry date", "added"]),
        ("date_started", ["date started", "started"]),
        ("date_finished", ["date finished", "last date read", "date read", "finished"]),
    ]
    date_fields = ["date_added", "date_started", "date_finished"]
    shelf_mapping_guesses = {
        "to-read": ["to-read", "want to read"],
        "read": ["read", "already read"],
        "reading": ["currently-reading", "reading", "currently reading"],
    }

    def create_job(self, user, csv_file, include_reviews, privacy):
        """check over a csv and creates a database entry for the job"""
        csv_reader = csv.DictReader(csv_file, delimiter=self.delimiter)
        rows = enumerate(list(csv_reader))
        job = ImportJob.objects.create(
            user=user,
            include_reviews=include_reviews,
            privacy=privacy,
            mappings=self.create_row_mappings(csv_reader.fieldnames),
            source=self.service,
        )

        for index, entry in rows:
            self.create_item(job, index, entry)
        return job

    def update_legacy_job(self, job):
        """patch up a job that was in the old format"""
        items = job.items
        headers = list(items.first().data.keys())
        job.mappings = self.create_row_mappings(headers)
        job.updated_date = timezone.now()
        job.save()

        for item in items.all():
            normalized = self.normalize_row(item.data, job.mappings)
            normalized["shelf"] = self.get_shelf(normalized)
            item.normalized_data = normalized
            item.save()

    def create_row_mappings(self, headers):
        """guess what the headers mean"""
        mappings = {}
        for (key, guesses) in self.row_mappings_guesses:
            value = [h for h in headers if h.lower() in guesses]
            value = value[0] if len(value) else None
            if value:
                headers.remove(value)
            mappings[key] = value
        return mappings

    def create_item(self, job, index, data):
        """creates and saves an import item"""
        normalized = self.normalize_row(data, job.mappings)
        normalized["shelf"] = self.get_shelf(normalized)
        ImportItem(job=job, index=index, data=data, normalized_data=normalized).save()

    def get_shelf(self, normalized_row):
        """determine which shelf to use"""
        shelf_name = normalized_row.get("shelf")
        if not shelf_name:
            return None
        shelf_name = shelf_name.lower()
        shelf = [
            s for (s, gs) in self.shelf_mapping_guesses.items() if shelf_name in gs
        ]
        return shelf[0] if shelf else None

    def normalize_row(self, entry, mappings):  # pylint: disable=no-self-use
        """use the dataclass to create the formatted row of data"""
        return {k: entry.get(v) for k, v in mappings.items()}

    def create_retry_job(self, user, original_job, items):
        """retry items that didn't import"""
        job = ImportJob.objects.create(
            user=user,
            include_reviews=original_job.include_reviews,
            privacy=original_job.privacy,
            source=original_job.source,
            # TODO: allow users to adjust mappings
            mappings=original_job.mappings,
            retry=True,
        )
        for item in items:
            # this will re-normalize the raw data
            self.create_item(job, item.index, item.data)
        return job
