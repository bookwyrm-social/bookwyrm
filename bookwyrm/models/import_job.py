""" track progress of goodreads imports """
import re
import dateutil.parser

from django.db import models
from django.utils import timezone

from bookwyrm.connectors import connector_manager
from bookwyrm.models import ReadThrough, User, Book, Edition
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


class ImportJob(models.Model):
    """entry for a specific request for book data import"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_date = models.DateTimeField(default=timezone.now)
    updated_date = models.DateTimeField(default=timezone.now)
    include_reviews = models.BooleanField(default=True)
    mappings = models.JSONField()
    complete = models.BooleanField(default=False)
    source = models.CharField(max_length=100)
    privacy = models.CharField(
        max_length=255, default="public", choices=PrivacyLevels.choices
    )
    retry = models.BooleanField(default=False)

    @property
    def pending_items(self):
        """items that haven't been processed yet"""
        return self.items.filter(fail_reason__isnull=True, book__isnull=True)


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

    def update_job(self):
        """let the job know when the items get work done"""
        job = self.job
        job.updated_date = timezone.now()
        job.save()
        if not job.pending_items.exists() and not job.complete:
            job.complete = True
            job.save(update_fields=["complete"])

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
            return timezone.make_aware(
                dateutil.parser.parse(self.normalized_data.get("date_added"))
            )
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
