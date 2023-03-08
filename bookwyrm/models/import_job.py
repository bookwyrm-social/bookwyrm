""" track progress of goodreads imports """
import math
import re
import dateutil.parser

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from bookwyrm.connectors import connector_manager
from bookwyrm.models import (
    User,
    Book,
    Edition,
    Work,
    ShelfBook,
    Shelf,
    ReadThrough,
    Review,
    ReviewRating,
)
from bookwyrm.tasks import app, LOW, IMPORTS
from .fields import PrivacyLevels


def unquote_string(text):
    """resolve csv quote weirdness"""
    if not text:
        return None
    match = re.match(r'="([^"]*)"', text)
    if match:
        return match.group(1)
    return text


def construct_search_term(title, author):
    """formulate a query for the data connector"""
    # Strip brackets (usually series title from search term)
    title = re.sub(r"\s*\([^)]*\)\s*", "", title)
    # Open library doesn't like including author initials in search term.
    author = re.sub(r"(\w\.)+\s*", "", author) if author else ""

    return " ".join([title, author])


ImportStatuses = [
    ("pending", _("Pending")),
    ("active", _("Active")),
    ("complete", _("Complete")),
    ("stopped", _("Stopped")),
]


class ImportJob(models.Model):
    """entry for a specific request for book data import"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_date = models.DateTimeField(default=timezone.now)
    updated_date = models.DateTimeField(default=timezone.now)
    include_reviews = models.BooleanField(default=True)
    mappings = models.JSONField()
    source = models.CharField(max_length=100)
    privacy = models.CharField(max_length=255, default="public", choices=PrivacyLevels)
    retry = models.BooleanField(default=False)
    task_id = models.CharField(max_length=200, null=True, blank=True)

    complete = models.BooleanField(default=False)
    status = models.CharField(
        max_length=50, choices=ImportStatuses, default="pending", null=True
    )

    def start_job(self):
        """Report that the job has started"""
        task = start_import_task.delay(self.id)
        self.task_id = task.id

        self.save(update_fields=["task_id"])

    def complete_job(self):
        """Report that the job has completed"""
        self.status = "complete"
        self.complete = True
        self.pending_items.update(fail_reason=_("Import stopped"))
        self.save(update_fields=["status", "complete"])

    def stop_job(self):
        """Stop the job"""
        self.status = "stopped"
        self.complete = True
        self.save(update_fields=["status", "complete"])
        self.pending_items.update(fail_reason=_("Import stopped"))

        # stop starting
        app.control.revoke(self.task_id, terminate=True)
        tasks = self.pending_items.filter(task_id__isnull=False).values_list(
            "task_id", flat=True
        )
        app.control.revoke(list(tasks))

    @property
    def pending_items(self):
        """items that haven't been processed yet"""
        return self.items.filter(fail_reason__isnull=True, book__isnull=True)

    @property
    def item_count(self):
        """How many books do you want to import???"""
        return self.items.count()

    @property
    def percent_complete(self):
        """How far along?"""
        item_count = self.item_count
        if not item_count:
            return 0
        return math.floor((item_count - self.pending_item_count) / item_count * 100)

    @property
    def pending_item_count(self):
        """And how many pending items??"""
        return self.pending_items.count()

    @property
    def successful_item_count(self):
        """How many found a book?"""
        return self.items.filter(book__isnull=False).count()

    @property
    def failed_item_count(self):
        """How many found a book?"""
        return self.items.filter(fail_reason__isnull=False).count()


class ImportItem(models.Model):
    """a single line of a csv being imported"""

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="items")
    index = models.IntegerField()
    data = models.JSONField()
    normalized_data = models.JSONField()
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True)
    book_guess = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="book_guess",
    )
    fail_reason = models.TextField(null=True)
    linked_review = models.ForeignKey(
        "Review", on_delete=models.SET_NULL, null=True, blank=True
    )
    task_id = models.CharField(max_length=200, null=True, blank=True)

    def update_job(self):
        """let the job know when the items get work done"""
        job = self.job
        if job.complete:
            return

        job.updated_date = timezone.now()
        job.save()
        if not job.pending_items.exists() and not job.complete:
            job.complete_job()

    def resolve(self):
        """try various ways to lookup a book"""
        # we might be calling this after manually adding the book,
        # so no need to do searches
        if self.book:
            return

        if self.isbn:
            self.book = self.get_book_from_identifier()
        elif self.openlibrary_key:
            self.book = self.get_book_from_identifier(field="openlibrary_key")
        else:
            # don't fall back on title/author search if isbn is present.
            # you're too likely to mismatch
            book, confidence = self.get_book_from_title_author()
            if confidence > 0.999:
                self.book = book
            else:
                self.book_guess = book

    def get_book_from_identifier(self, field="isbn"):
        """search by isbn or other unique identifier"""
        search_result = connector_manager.first_search_result(
            getattr(self, field), min_confidence=0.999
        )
        if search_result:
            # it's already in the right format
            if isinstance(search_result, Edition):
                return search_result
            # it's just a search result, book needs to be created
            # raises ConnectorException
            return search_result.connector.get_or_create_book(search_result.key)
        return None

    def get_book_from_title_author(self):
        """search by title and author"""
        if not self.title:
            return None, 0
        search_term = construct_search_term(self.title, self.author)
        search_result = connector_manager.first_search_result(
            search_term, min_confidence=0.1
        )
        if search_result:
            if isinstance(search_result, Edition):
                return (search_result, 1)
            # raises ConnectorException
            return (
                search_result.connector.get_or_create_book(search_result.key),
                search_result.confidence,
            )
        return None, 0

    @property
    def title(self):
        """get the book title"""
        return self.normalized_data.get("title")

    @property
    def author(self):
        """get the book's authors"""
        return self.normalized_data.get("authors")

    @property
    def isbn(self):
        """pulls out the isbn13 field from the csv line data"""
        return unquote_string(self.normalized_data.get("isbn_13")) or unquote_string(
            self.normalized_data.get("isbn_10")
        )

    @property
    def openlibrary_key(self):
        """the edition identifier is preferable to the work key"""
        return self.normalized_data.get("openlibrary_key") or self.normalized_data.get(
            "openlibrary_work_key"
        )

    @property
    def shelf(self):
        """the goodreads shelf field"""
        return self.normalized_data.get("shelf")

    @property
    def review(self):
        """a user-written review, to be imported with the book data"""
        return self.normalized_data.get("review_body")

    @property
    def rating(self):
        """x/5 star rating for a book"""
        if self.normalized_data.get("rating"):
            return float(self.normalized_data.get("rating"))
        return None

    @property
    def date_added(self):
        """when the book was added to this dataset"""
        if self.normalized_data.get("date_added"):
            parsed_date_added = dateutil.parser.parse(
                self.normalized_data.get("date_added")
            )

            if timezone.is_aware(parsed_date_added):
                # Keep timezone if import already had one
                return parsed_date_added

            return timezone.make_aware(parsed_date_added)
        return None

    @property
    def date_started(self):
        """when the book was started"""
        if self.normalized_data.get("date_started"):
            return timezone.make_aware(
                dateutil.parser.parse(self.normalized_data.get("date_started"))
            )
        return None

    @property
    def date_read(self):
        """the date a book was completed"""
        if self.normalized_data.get("date_finished"):
            return timezone.make_aware(
                dateutil.parser.parse(self.normalized_data.get("date_finished"))
            )
        return None

    @property
    def reads(self):
        """formats a read through dataset for the book in this line"""
        start_date = self.date_started

        # Goodreads special case (no 'date started' field)
        if (
            (self.shelf == "reading" or (self.shelf == "read" and self.date_read))
            and self.date_added
            and not start_date
        ):
            start_date = self.date_added

        if start_date and start_date is not None and not self.date_read:
            return [ReadThrough(start_date=start_date)]
        if self.date_read:
            start_date = (
                start_date if start_date and start_date < self.date_read else None
            )
            return [
                ReadThrough(
                    start_date=start_date,
                    finish_date=self.date_read,
                )
            ]
        return []

    def __repr__(self):
        # pylint: disable=consider-using-f-string
        return "<{!r} Item {!r}>".format(self.index, self.normalized_data.get("title"))

    def __str__(self):
        # pylint: disable=consider-using-f-string
        return "{} by {}".format(
            self.normalized_data.get("title"), self.normalized_data.get("authors")
        )


@app.task(queue=IMPORTS, ignore_result=True)
def start_import_task(job_id):
    """trigger the child tasks for each row"""
    job = ImportJob.objects.get(id=job_id)
    job.status = "active"
    job.save(update_fields=["status"])
    # don't start the job if it was stopped from the UI
    if job.complete:
        return

    # these are sub-tasks so that one big task doesn't use up all the memory in celery
    for item in job.items.all():
        task = import_item_task.delay(item.id)
        item.task_id = task.id
        item.save()
    job.status = "active"
    job.save()


@app.task(queue=IMPORTS, ignore_result=True)
def import_item_task(item_id):
    """resolve a row into a book"""
    item = ImportItem.objects.get(id=item_id)
    # make sure the job has not been stopped
    if item.job.complete:
        return

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
    if job.complete:
        return

    user = job.user
    if isinstance(item.book, Work):
        item.book = item.book.default_edition
    if not item.book:
        item.fail_reason = _("Error loading book")
        item.save()
        return
    if not isinstance(item.book, Edition):
        item.book = item.book.edition

    existing_shelf = ShelfBook.objects.filter(book=item.book, user=user).exists()

    # shelve the book if it hasn't been shelved already
    if item.shelf and not existing_shelf:
        desired_shelf = Shelf.objects.get(identifier=item.shelf, user=user)
        shelved_date = item.date_added or timezone.now()
        ShelfBook(
            book=item.book, shelf=desired_shelf, user=user, shelved_date=shelved_date
        ).save(priority=LOW)

    for read in item.reads:
        # check for an existing readthrough with the same dates
        if ReadThrough.objects.filter(
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
            review = Review.objects.filter(
                user=user,
                book=item.book,
                name=review_title,
                rating=item.rating,
                published_date=published_date_guess,
            ).first()
            if not review:
                review = Review(
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
            review = ReviewRating.objects.filter(
                user=user,
                book=item.book,
                published_date=published_date_guess,
                rating=item.rating,
            ).first()
            if not review:
                review = ReviewRating(
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
