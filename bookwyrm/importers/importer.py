""" handle reading a csv from an external service, defaults are from Goodreads """
import csv
from datetime import timedelta
from typing import Iterable, Optional

from django.utils import timezone
from bookwyrm.models import ImportJob, ImportItem, SiteSettings, User


class Importer:
    """Generic class for csv data import from an outside service"""

    service = "Import"
    delimiter = ","
    encoding = "UTF-8"

    # these are from Goodreads
    row_mappings_guesses = [
        ("id", ["id", "book id"]),
        ("title", ["title"]),
        ("authors", ["author_text", "author", "authors", "primary author"]),
        ("isbn_10", ["isbn_10", "isbn10", "isbn", "isbn/uid"]),
        ("isbn_13", ["isbn_13", "isbn13", "isbn", "isbns", "isbn/uid"]),
        ("shelf", ["shelf", "exclusive shelf", "read status", "bookshelf"]),
        ("review_name", ["review_name", "review name"]),
        ("review_body", ["review_content", "my review", "review"]),
        ("rating", ["my rating", "rating", "star rating"]),
        (
            "date_added",
            ["shelf_date", "date_added", "date added", "entry date", "added"],
        ),
        ("date_started", ["start_date", "date started", "started"]),
        (
            "date_finished",
            ["finish_date", "date finished", "last date read", "date read", "finished"],
        ),
    ]

    # TODO: stopped

    date_fields = ["date_added", "date_started", "date_finished"]
    shelf_mapping_guesses = {
        "to-read": ["to-read", "want to read"],
        "read": ["read", "already read"],
        "reading": ["currently-reading", "reading", "currently reading"],
    }

    # pylint: disable=too-many-arguments
    def create_job(
        self,
        user: User,
        csv_file: Iterable[str],
        include_reviews: bool,
        privacy: str,
        create_shelves: bool = True,
    ) -> ImportJob:
        """check over a csv and creates a database entry for the job"""
        csv_reader = csv.DictReader(csv_file, delimiter=self.delimiter)
        rows = list(csv_reader)
        if len(rows) < 1:
            raise ValueError("CSV file is empty")

        mappings = (
            self.create_row_mappings(list(fieldnames))
            if (fieldnames := csv_reader.fieldnames)
            else {}
        )

        job = ImportJob.objects.create(
            user=user,
            include_reviews=include_reviews,
            create_shelves=create_shelves,
            privacy=privacy,
            mappings=mappings,
            source=self.service,
        )

        enforce_limit, allowed_imports = self.get_import_limit(user)
        if enforce_limit and allowed_imports <= 0:
            job.complete_job()
            return job
        for index, entry in enumerate(rows):
            if enforce_limit and index >= allowed_imports:
                break
            self.create_item(job, index, entry)
        return job

    def update_legacy_job(self, job: ImportJob) -> None:
        """patch up a job that was in the old format"""
        items = job.items
        first_item = items.first()
        if first_item is None:
            return

        headers = list(first_item.data.keys())
        job.mappings = self.create_row_mappings(headers)
        job.updated_date = timezone.now()
        job.save()

        for item in items.all():
            normalized = self.normalize_row(item.data, job.mappings)
            normalized["shelf"] = self.get_shelf(normalized)
            item.normalized_data = normalized
            item.save()

    def create_row_mappings(self, headers: list[str]) -> dict[str, Optional[str]]:
        """guess what the headers mean"""
        mappings = {}
        for (key, guesses) in self.row_mappings_guesses:
            values = [h for h in headers if h.lower() in guesses]
            value = values[0] if len(values) else None
            if value:
                headers.remove(value)
            mappings[key] = value
        return mappings

    def create_item(self, job: ImportJob, index: int, data: dict[str, str]) -> None:
        """creates and saves an import item"""
        normalized = self.normalize_row(data, job.mappings)
        normalized["shelf"] = self.get_shelf(normalized)
        ImportItem(job=job, index=index, data=data, normalized_data=normalized).save()

    def get_shelf(self, normalized_row: dict[str, Optional[str]]) -> Optional[str]:
        """determine which shelf to use"""
        shelf_name = normalized_row.get("shelf")
        if not shelf_name:
            return None
        shelf_name = shelf_name.lower()
        shelf = [
            s for (s, gs) in self.shelf_mapping_guesses.items() if shelf_name in gs
        ]
        return shelf[0] if shelf else normalized_row.get("shelf") or None

    # pylint: disable=no-self-use
    def normalize_row(
        self, entry: dict[str, str], mappings: dict[str, Optional[str]]
    ) -> dict[str, Optional[str]]:
        """use the dataclass to create the formatted row of data"""
        return {k: entry.get(v) if v else None for k, v in mappings.items()}

    # pylint: disable=no-self-use
    def get_import_limit(self, user: User) -> tuple[int, int]:
        """check if import limit is set and return how many imports are left"""
        site_settings = SiteSettings.objects.get()
        import_size_limit = site_settings.import_size_limit
        import_limit_reset = site_settings.import_limit_reset
        enforce_limit = import_size_limit and import_limit_reset
        allowed_imports = 0

        if enforce_limit:
            time_range = timezone.now() - timedelta(days=import_limit_reset)
            import_jobs = ImportJob.objects.filter(
                user=user, created_date__gte=time_range
            )
            # pylint: disable=consider-using-generator
            imported_books = sum([job.successful_item_count for job in import_jobs])
            allowed_imports = import_size_limit - imported_books
        return enforce_limit, allowed_imports

    def create_retry_job(
        self, user: User, original_job: ImportJob, items: list[ImportItem]
    ) -> ImportJob:
        """retry items that didn't import"""
        job = ImportJob.objects.create(
            user=user,
            include_reviews=original_job.include_reviews,
            create_shelves=original_job.create_shelves,
            privacy=original_job.privacy,
            source=original_job.source,
            # TODO: allow users to adjust mappings
            mappings=original_job.mappings,
            retry=True,
        )
        enforce_limit, allowed_imports = self.get_import_limit(user)
        if enforce_limit and allowed_imports <= 0:
            job.complete_job()
            return job
        for index, item in enumerate(items):
            if enforce_limit and index >= allowed_imports:
                break
            # this will re-normalize the raw data
            self.create_item(job, item.index, item.data)
        return job
