""" track progress of goodreads imports """
import re
import dateutil.parser

from django.apps import apps
from django.db import models
from django.utils import timezone

from bookwyrm.connectors import connector_manager
from bookwyrm.models import ReadThrough, User, Book
from .fields import PrivacyLevels


# Mapping goodreads -> bookwyrm shelf titles.
GOODREADS_SHELVES = {
    "read": "read",
    "currently-reading": "reading",
    "to-read": "to-read",
}


def unquote_string(text):
    """resolve csv quote weirdness"""
    match = re.match(r'="([^"]*)"', text)
    if match:
        return match.group(1)
    return text


def construct_search_term(title, author):
    """formulate a query for the data connector"""
    # Strip brackets (usually series title from search term)
    title = re.sub(r"\s*\([^)]*\)\s*", "", title)
    # Open library doesn't like including author initials in search term.
    author = re.sub(r"(\w\.)+\s*", "", author)

    return " ".join([title, author])


class ImportJob(models.Model):
    """entry for a specific request for book data import"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_date = models.DateTimeField(default=timezone.now)
    task_id = models.CharField(max_length=100, null=True)
    include_reviews = models.BooleanField(default=True)
    complete = models.BooleanField(default=False)
    privacy = models.CharField(
        max_length=255, default="public", choices=PrivacyLevels.choices
    )
    retry = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """save and notify"""
        super().save(*args, **kwargs)
        if self.complete:
            notification_model = apps.get_model(
                "bookwyrm.Notification", require_ready=True
            )
            notification_model.objects.create(
                user=self.user,
                notification_type="IMPORT",
                related_import=self,
            )


class ImportItem(models.Model):
    """a single line of a csv being imported"""

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="items")
    index = models.IntegerField()
    data = models.JSONField()
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True)
    fail_reason = models.TextField(null=True)

    def resolve(self):
        """try various ways to lookup a book"""
        if self.isbn:
            self.book = self.get_book_from_isbn()
        else:
            # don't fall back on title/author search is isbn is present.
            # you're too likely to mismatch
            self.get_book_from_title_author()

    def get_book_from_isbn(self):
        """search by isbn"""
        search_result = connector_manager.first_search_result(
            self.isbn, min_confidence=0.999
        )
        if search_result:
            # raises ConnectorException
            return search_result.connector.get_or_create_book(search_result.key)
        return None

    def get_book_from_title_author(self):
        """search by title and author"""
        search_term = construct_search_term(self.title, self.author)
        search_result = connector_manager.first_search_result(
            search_term, min_confidence=0.999
        )
        if search_result:
            # raises ConnectorException
            return search_result.connector.get_or_create_book(search_result.key)
        return None

    @property
    def title(self):
        """get the book title"""
        return self.data["Title"]

    @property
    def author(self):
        """get the book title"""
        return self.data["Author"]

    @property
    def isbn(self):
        """pulls out the isbn13 field from the csv line data"""
        return unquote_string(self.data["ISBN13"])

    @property
    def shelf(self):
        """the goodreads shelf field"""
        if self.data["Exclusive Shelf"]:
            return GOODREADS_SHELVES.get(self.data["Exclusive Shelf"])
        return None

    @property
    def review(self):
        """a user-written review, to be imported with the book data"""
        return self.data["My Review"]

    @property
    def rating(self):
        """x/5 star rating for a book"""
        if self.data.get("My Rating", None):
            return int(self.data["My Rating"])
        return None

    @property
    def date_added(self):
        """when the book was added to this dataset"""
        if self.data["Date Added"]:
            return timezone.make_aware(dateutil.parser.parse(self.data["Date Added"]))
        return None

    @property
    def date_started(self):
        """when the book was started"""
        if "Date Started" in self.data and self.data["Date Started"]:
            return timezone.make_aware(dateutil.parser.parse(self.data["Date Started"]))
        return None

    @property
    def date_read(self):
        """the date a book was completed"""
        if self.data["Date Read"]:
            return timezone.make_aware(dateutil.parser.parse(self.data["Date Read"]))
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
            return [
                ReadThrough(
                    start_date=start_date,
                    finish_date=self.date_read,
                )
            ]
        return []

    def __repr__(self):
        return "<{!r}Item {!r}>".format(self.data["import_source"], self.data["Title"])

    def __str__(self):
        return "{} by {}".format(self.data["Title"], self.data["Author"])
