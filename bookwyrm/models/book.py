""" database schema for books and shelves """
import re

from django.db import models
from model_utils.managers import InheritanceManager

from bookwyrm import activitypub
from bookwyrm.settings import DOMAIN, DEFAULT_LANGUAGE

from .activitypub_mixin import OrderedCollectionPageMixin, ObjectMixin
from .base_model import BookWyrmModel
from . import fields


class BookDataModel(ObjectMixin, BookWyrmModel):
    """fields shared between editable book data (books, works, authors)"""

    origin_id = models.CharField(max_length=255, null=True, blank=True)
    openlibrary_key = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    inventaire_id = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    librarything_key = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    goodreads_key = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    bnf_id = fields.CharField(  # Bibliothèque nationale de France
        max_length=255, blank=True, null=True, deduplication_field=True
    )

    last_edited_by = fields.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        null=True,
    )

    class Meta:
        """can't initialize this model, that wouldn't make sense"""

        abstract = True

    def save(self, *args, **kwargs):
        """ensure that the remote_id is within this instance"""
        if self.id:
            self.remote_id = self.get_remote_id()
        else:
            self.origin_id = self.remote_id
            self.remote_id = None
        return super().save(*args, **kwargs)

    def broadcast(self, activity, sender, software="bookwyrm"):
        """only send book data updates to other bookwyrm instances"""
        super().broadcast(activity, sender, software=software)


class Book(BookDataModel):
    """a generic book, which can mean either an edition or a work"""

    connector = models.ForeignKey("Connector", on_delete=models.PROTECT, null=True)

    # book/work metadata
    title = fields.TextField(max_length=255)
    sort_title = fields.CharField(max_length=255, blank=True, null=True)
    subtitle = fields.TextField(max_length=255, blank=True, null=True)
    description = fields.HtmlField(blank=True, null=True)
    languages = fields.ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    series = fields.TextField(max_length=255, blank=True, null=True)
    series_number = fields.CharField(max_length=255, blank=True, null=True)
    subjects = fields.ArrayField(
        models.CharField(max_length=255), blank=True, null=True, default=list
    )
    subject_places = fields.ArrayField(
        models.CharField(max_length=255), blank=True, null=True, default=list
    )
    authors = fields.ManyToManyField("Author")
    cover = fields.ImageField(
        upload_to="covers/", blank=True, null=True, alt_field="alt_text"
    )
    first_published_date = fields.DateTimeField(blank=True, null=True)
    published_date = fields.DateTimeField(blank=True, null=True)

    objects = InheritanceManager()

    @property
    def author_text(self):
        """format a list of authors"""
        return ", ".join(a.name for a in self.authors.all())

    @property
    def latest_readthrough(self):
        """most recent readthrough activity"""
        return self.readthrough_set.order_by("-updated_date").first()

    @property
    def edition_info(self):
        """properties of this edition, as a string"""
        items = [
            self.physical_format if hasattr(self, "physical_format") else None,
            self.languages[0] + " language"
            if self.languages and self.languages[0] != "English"
            else None,
            str(self.published_date.year) if self.published_date else None,
            ", ".join(self.publishers) if hasattr(self, "publishers") else None,
        ]
        return ", ".join(i for i in items if i)

    @property
    def alt_text(self):
        """image alt test"""
        text = "%s" % self.title
        if self.edition_info:
            text += " (%s)" % self.edition_info
        return text

    def save(self, *args, **kwargs):
        """can't be abstract for query reasons, but you shouldn't USE it"""
        if not isinstance(self, Edition) and not isinstance(self, Work):
            raise ValueError("Books should be added as Editions or Works")
        return super().save(*args, **kwargs)

    def get_remote_id(self):
        """editions and works both use "book" instead of model_name"""
        return "https://%s/book/%d" % (DOMAIN, self.id)

    def __repr__(self):
        return "<{} key={!r} title={!r}>".format(
            self.__class__,
            self.openlibrary_key,
            self.title,
        )


class Work(OrderedCollectionPageMixin, Book):
    """a work (an abstract concept of a book that manifests in an edition)"""

    # library of congress catalog control number
    lccn = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )

    def save(self, *args, **kwargs):
        """set some fields on the edition object"""
        # set rank
        for edition in self.editions.all():
            edition.save()
        return super().save(*args, **kwargs)

    @property
    def default_edition(self):
        """in case the default edition is not set"""
        return self.editions.order_by("-edition_rank").first()

    def to_edition_list(self, **kwargs):
        """an ordered collection of editions"""
        return self.to_ordered_collection(
            self.editions.order_by("-edition_rank").all(),
            remote_id="%s/editions" % self.remote_id,
            **kwargs,
        )

    activity_serializer = activitypub.Work
    serialize_reverse_fields = [("editions", "editions", "-edition_rank")]
    deserialize_reverse_fields = [("editions", "editions")]


class Edition(Book):
    """an edition of a book"""

    # these identifiers only apply to editions, not works
    isbn_10 = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    isbn_13 = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    oclc_number = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    asin = fields.CharField(
        max_length=255, blank=True, null=True, deduplication_field=True
    )
    pages = fields.IntegerField(blank=True, null=True)
    physical_format = fields.CharField(max_length=255, blank=True, null=True)
    publishers = fields.ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    shelves = models.ManyToManyField(
        "Shelf",
        symmetrical=False,
        through="ShelfBook",
        through_fields=("book", "shelf"),
    )
    parent_work = fields.ForeignKey(
        "Work",
        on_delete=models.PROTECT,
        null=True,
        related_name="editions",
        activitypub_field="work",
    )
    edition_rank = fields.IntegerField(default=0)

    activity_serializer = activitypub.Edition
    name_field = "title"

    def get_rank(self):
        """calculate how complete the data is on this edition"""
        rank = 0
        # big ups for havinga  cover
        rank += int(bool(self.cover)) * 3
        # is it in the instance's preferred language?
        rank += int(bool(DEFAULT_LANGUAGE in self.languages))
        # prefer print editions
        if self.physical_format:
            rank += int(
                bool(self.physical_format.lower() in ["paperback", "hardcover"])
            )

        # does it have metadata?
        rank += int(bool(self.isbn_13))
        rank += int(bool(self.isbn_10))
        rank += int(bool(self.oclc_number))
        rank += int(bool(self.pages))
        rank += int(bool(self.physical_format))
        rank += int(bool(self.description))
        # max rank is 9
        return rank

    def save(self, *args, **kwargs):
        """set some fields on the edition object"""
        # calculate isbn 10/13
        if self.isbn_13 and self.isbn_13[:3] == "978" and not self.isbn_10:
            self.isbn_10 = isbn_13_to_10(self.isbn_13)
        if self.isbn_10 and not self.isbn_13:
            self.isbn_13 = isbn_10_to_13(self.isbn_10)

        # normalize isbn format
        if self.isbn_10:
            self.isbn_10 = re.sub(r"[^0-9X]", "", self.isbn_10)
        if self.isbn_13:
            self.isbn_13 = re.sub(r"[^0-9X]", "", self.isbn_13)

        # set rank
        self.edition_rank = self.get_rank()

        return super().save(*args, **kwargs)


def isbn_10_to_13(isbn_10):
    """convert an isbn 10 into an isbn 13"""
    isbn_10 = re.sub(r"[^0-9X]", "", isbn_10)
    # drop the last character of the isbn 10 number (the original checkdigit)
    converted = isbn_10[:9]
    # add "978" to the front
    converted = "978" + converted
    # add a check digit to the end
    # multiply the odd digits by 1 and the even digits by 3 and sum them
    try:
        checksum = sum(int(i) for i in converted[::2]) + sum(
            int(i) * 3 for i in converted[1::2]
        )
    except ValueError:
        return None
    # add the checksum mod 10 to the end
    checkdigit = checksum % 10
    if checkdigit != 0:
        checkdigit = 10 - checkdigit
    return converted + str(checkdigit)


def isbn_13_to_10(isbn_13):
    """convert isbn 13 to 10, if possible"""
    if isbn_13[:3] != "978":
        return None

    isbn_13 = re.sub(r"[^0-9X]", "", isbn_13)

    # remove '978' and old checkdigit
    converted = isbn_13[3:-1]
    # calculate checkdigit
    # multiple each digit by 10,9,8.. successively and sum them
    try:
        checksum = sum(int(d) * (10 - idx) for (idx, d) in enumerate(converted))
    except ValueError:
        return None
    checkdigit = checksum % 11
    checkdigit = 11 - checkdigit
    if checkdigit == 10:
        checkdigit = "X"
    return converted + str(checkdigit)
