""" handle reading a tsv from librarything """
import re

from bookwyrm.models import Shelf

from . import Importer


class LibrarythingImporter(Importer):
    """csv downloads from librarything"""

    service = "LibraryThing"
    delimiter = "\t"
    encoding = "ISO-8859-1"

    def normalize_row(self, entry, mappings):  # pylint: disable=no-self-use
        """use the dataclass to create the formatted row of data"""
        remove_brackets = lambda v: re.sub(r"\[|\]", "", v) if v else None
        normalized = {k: remove_brackets(entry.get(v)) for k, v in mappings.items()}
        isbn_13 = normalized.get("isbn_13")
        isbn_13 = isbn_13.split(", ") if isbn_13 else []
        normalized["isbn_13"] = isbn_13[1] if len(isbn_13) > 1 else None
        return normalized

    def get_shelf(self, normalized_row):
        if normalized_row["date_finished"]:
            return Shelf.READ_FINISHED
        if normalized_row["date_started"]:
            return Shelf.READING
        return Shelf.TO_READ
