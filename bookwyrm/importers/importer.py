""" handle reading a csv from an external service, defaults are from Goodreads """
import csv
from dataclasses import dataclass
import logging

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from bookwyrm.models import ImportJob, ImportItem
from bookwyrm.tasks import app

logger = logging.getLogger(__name__)


class Importer:
    """Generic class for csv data import from an outside service"""

    service = "Unknown"
    delimiter = ","
    encoding = "UTF-8"

    # these are from Goodreads
    row_mappings_guesses = {
        "id": ["id", "book id"],
        "title": ["title"],
        "authors": ["author", "authors", "primary author"],
        "isbn_13": ["isbn13", "isbn"],
        "isbn_10": ["isbn10", "isbn"],
        "shelf": ["shelf", "exclusive shelf", "read status"],
        "review_name": ["review name"],
        "review_body": ["my review", "review"],
        "rating": ["my rating", "rating", "star rating"],
        "date_added": ["date added", "entry date", "added"],
        "date_started": ["date started", "started"],
        "date_finished": ["date finished", "last date read", "date read", "finished"],
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
        )

        for index, entry in rows:
            self.create_item(job, index, entry)
        return job

    def create_row_mappings(self, headers):
        """guess what the headers mean"""
        mappings = {}
        for (key, guesses) in self.row_mappings_guesses.items():
            value = [h for h in headers if h.lower() in guesses]
            value = value[0] if len(value) else None
            if value:
                headers.remove(value)
            mappings[key] = value
        return mappings

    def create_item(self, job, index, data):
        """creates and saves an import item"""
        normalized = self.normalize_row(data, job.mappings)
        ImportItem(job=job, index=index, data=data, normalized_data=normalized).save()

    def normalize_row(self, entry, mappings):  # pylint: disable=no-self-use
        """use the dataclass to create the formatted row of data"""
        return {k: entry.get(v) for k, v in mappings.items()}

    def create_retry_job(self, user, original_job, items):
        """retry items that didn't import"""
        job = ImportJob.objects.create(
            user=user,
            include_reviews=original_job.include_reviews,
            privacy=original_job.privacy,
            # TODO: allow users to adjust mappings
            mappings=original_job.mappings,
            retry=True,
        )
        for item in items:
            # this will re-normalize the raw data
            self.create_item(job, item.index, item.data)
        return job

    def start_import(self, job):
        """initalizes a csv import job"""
        result = import_data.delay(self.service, job.id)
        job.task_id = result.id
        job.save()


@app.task(queue="low_priority")
def import_data(source, job_id):
    """does the actual lookup work in a celery task"""
    job = ImportJob.objects.get(id=job_id)
    try:
        for item in job.items.all():
            try:
                item.resolve()
            except Exception as err:  # pylint: disable=broad-except
                logger.exception(err)
                item.fail_reason = _("Error loading book")
                item.save()
                continue

            if item.book or item.book_guess:
                item.save()

            if item.book:
                # shelves book and handles reviews
                handle_imported_book(
                    source, job.user, item, job.include_reviews, job.privacy
                )
            else:
                item.fail_reason = _("Could not find a match for book")
                item.save()
    finally:
        job.complete = True
        job.save()


def handle_imported_book(source, user, item, include_reviews, privacy):
    """process a csv and then post about it"""
    if isinstance(item.book, models.Work):
        item.book = item.book.default_edition
    if not item.book:
        return

    existing_shelf = models.ShelfBook.objects.filter(book=item.book, user=user).exists()

    # shelve the book if it hasn't been shelved already
    if item.shelf and not existing_shelf:
        desired_shelf = models.Shelf.objects.get(identifier=item.shelf, user=user)
        shelved_date = item.date_added or timezone.now()
        models.ShelfBook.objects.create(
            book=item.book, shelf=desired_shelf, user=user, shelved_date=shelved_date
        )

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

    if include_reviews and (item.rating or item.review):
        # we don't know the publication date of the review,
        # but "now" is a bad guess
        published_date_guess = item.date_read or item.date_added
        if item.review:
            # pylint: disable=consider-using-f-string
            review_title = (
                "Review of {!r} on {!r}".format(
                    item.book.title,
                    source,
                )
                if item.review
                else ""
            )
            review = models.Review(
                user=user,
                book=item.book,
                name=review_title,
                content=item.review,
                rating=item.rating,
                published_date=published_date_guess,
                privacy=privacy,
            )
        else:
            # just a rating
            review = models.ReviewRating(
                user=user,
                book=item.book,
                rating=item.rating,
                published_date=published_date_guess,
                privacy=privacy,
            )
        # only broadcast this review to other bookwyrm instances
        review.save(software="bookwyrm")


@dataclass
class ImportEntry:
    """data extracted from a line in a csv"""

    title: str
    authors: str = None
    isbn_13: str = None
    isbn_10: str = None
    shelf: str = None
    review_name: str = None
    review_rating: float = None
    review_body: str = None
    review_cw: str = None
    rating: float = None
    date_added: str = None
    date_started: str = None
    date_finished: str = None
    import_source: str = "Unknown"
