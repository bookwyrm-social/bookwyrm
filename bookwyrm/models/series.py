"""series of books"""

from django.db import models

from .base_model import BookWyrmModel
from . import fields


class Series(BookWyrmModel):
    """a named series of books"""

    name = fields.CharField(max_length=100)
    authors = fields.ManyToManyField("Author")  # TODO: add on Author model
    books = fields.ManyToManyField(
        "Book",
        through="SeriesBook",
        through_fields=("series", "book"),
        related_name="series_books",
    )


class SeriesBook(BookWyrmModel):
    """membership of a series"""

    book = models.ForeignKey("Book", on_delete=models.PROTECT)
    series = models.ForeignKey("Series", on_delete=models.PROTECT)
    number = fields.CharField(max_length=255, blank=True, null=True)

    collection_field = "series"

    class Meta:
        """a series can't contain the same book twice"""

        unique_together = ("book", "series")
        ordering = ["-number"]
