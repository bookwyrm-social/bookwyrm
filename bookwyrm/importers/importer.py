""" handle reading a csv from an external service, defaults are from GoodReads """
import csv
import logging

from bookwyrm import models
from bookwyrm.models import ImportJob, ImportItem
from bookwyrm.tasks import app

logger = logging.getLogger(__name__)


class Importer:
    """Generic class for csv data import from an outside service"""

    service = "Unknown"
    delimiter = ","
    encoding = "UTF-8"
    mandatory_fields = ["Title", "Author"]

    def create_job(self, user, csv_file, include_reviews, privacy):
        """check over a csv and creates a database entry for the job"""
        job = ImportJob.objects.create(
            user=user, include_reviews=include_reviews, privacy=privacy
        )
        for index, entry in enumerate(
            list(csv.DictReader(csv_file, delimiter=self.delimiter))
        ):
            if not all(x in entry for x in self.mandatory_fields):
                raise ValueError("Author and title must be in data.")
            entry = self.parse_fields(entry)
            self.save_item(job, index, entry)
        return job

    def save_item(self, job, index, data):  # pylint: disable=no-self-use
        """creates and saves an import item"""
        ImportItem(job=job, index=index, data=data).save()

    def parse_fields(self, entry):
        """updates csv data with additional info"""
        entry.update({"import_source": self.service})
        return entry

    def create_retry_job(self, user, original_job, items):
        """retry items that didn't import"""
        job = ImportJob.objects.create(
            user=user,
            include_reviews=original_job.include_reviews,
            privacy=original_job.privacy,
            retry=True,
        )
        for item in items:
            self.save_item(job, item.index, item.data)
        return job

    def start_import(self, job):
        """initalizes a csv import job"""
        result = import_data.delay(self.service, job.id)
        job.task_id = result.id
        job.save()


@app.task
def import_data(source, job_id):
    """does the actual lookup work in a celery task"""
    job = ImportJob.objects.get(id=job_id)
    try:
        for item in job.items.all():
            try:
                item.resolve()
            except Exception as e:  # pylint: disable=broad-except
                logger.exception(e)
                item.fail_reason = "Error loading book"
                item.save()
                continue

            if item.book:
                item.save()

                # shelves book and handles reviews
                handle_imported_book(
                    source, job.user, item, job.include_reviews, job.privacy
                )
            else:
                item.fail_reason = "Could not find a match for book"
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
        models.ShelfBook.objects.create(book=item.book, shelf=desired_shelf, user=user)

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
            review_title = (
                "Review of {!r} on {!r}".format(
                    item.book.title,
                    source,
                )
                if item.review
                else ""
            )
            models.Review.objects.create(
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
            models.ReviewRating.objects.create(
                user=user,
                book=item.book,
                rating=item.rating,
                published_date=published_date_guess,
                privacy=privacy,
            )
