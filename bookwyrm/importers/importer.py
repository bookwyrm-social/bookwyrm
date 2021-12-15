""" handle reading a csv from an external service, defaults are from Goodreads """
import csv
import logging

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from bookwyrm.models import ImportJob, ImportItem
from bookwyrm.tasks import app, LOW

logger = logging.getLogger(__name__)


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

    def start_import(self, job):  # pylint: disable=no-self-use
        """initalizes a csv import job"""
        result = start_import_task.delay(job.id)
        job.task_id = result.id
        job.save()


@app.task(queue="low_priority")
def start_import_task(job_id):
    """trigger the child tasks for each row"""
    job = ImportJob.objects.get(id=job_id)
    # these are sub-tasks so that one big task doesn't use up all the memory in celery
    for item in job.items.values_list("id", flat=True).all():
        import_item_task.delay(item)


@app.task(queue="low_priority")
def import_item_task(item_id):
    """resolve a row into a book"""
    item = models.ImportItem.objects.get(id=item_id)
    try:
        item.resolve()
    except Exception as err:  # pylint: disable=broad-except
        item.fail_reason = _("Error loading book")
        item.save()
        item.update_job()
        raise err

    if item.book:
        # shelves book and handles reviews
        handle_imported_book(item)
    else:
        item.fail_reason = _("Could not find a match for book")

    item.save()
    item.update_job()


def handle_imported_book(item):
    """process a csv and then post about it"""
    job = item.job
    user = job.user
    if isinstance(item.book, models.Work):
        item.book = item.book.default_edition
    if not item.book:
        item.fail_reason = _("Error loading book")
        item.save()
        return
    if not isinstance(item.book, models.Edition):
        item.book = item.book.edition

    existing_shelf = models.ShelfBook.objects.filter(book=item.book, user=user).exists()

    # shelve the book if it hasn't been shelved already
    if item.shelf and not existing_shelf:
        desired_shelf = models.Shelf.objects.get(identifier=item.shelf, user=user)
        shelved_date = item.date_added or timezone.now()
        models.ShelfBook(
            book=item.book, shelf=desired_shelf, user=user, shelved_date=shelved_date
        ).save(priority=LOW)

    for read in item.reads:
        # check for an existing readthrough with the same dates
        if models.ReadThrough.objects.filter(
            user=user,
            book=item.book,
            start_date=read.start_date,
            finish_date=read.finish_date,
        ).exists():
            continue
        read.book = item.book
        read.user = user
        read.save()

    if job.include_reviews and (item.rating or item.review) and not item.linked_review:
        # we don't know the publication date of the review,
        # but "now" is a bad guess
        published_date_guess = item.date_read or item.date_added
        if item.review:
            # pylint: disable=consider-using-f-string
            review_title = "Review of {!r} on {!r}".format(
                item.book.title,
                job.source,
            )
            review = models.Review.objects.filter(
                user=user,
                book=item.book,
                name=review_title,
                rating=item.rating,
                published_date=published_date_guess,
            ).first()
            if not review:
                review = models.Review(
                    user=user,
                    book=item.book,
                    name=review_title,
                    content=item.review,
                    rating=item.rating,
                    published_date=published_date_guess,
                    privacy=job.privacy,
                )
                review.save(software="bookwyrm", priority=LOW)
        else:
            # just a rating
            review = models.ReviewRating.objects.filter(
                user=user,
                book=item.book,
                published_date=published_date_guess,
                rating=item.rating,
            ).first()
            if not review:
                review = models.ReviewRating(
                    user=user,
                    book=item.book,
                    rating=item.rating,
                    published_date=published_date_guess,
                    privacy=job.privacy,
                )
                review.save(software="bookwyrm", priority=LOW)

        # only broadcast this review to other bookwyrm instances
        item.linked_review = review
    item.save()
