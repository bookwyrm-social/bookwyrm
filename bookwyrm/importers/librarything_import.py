"""handle reading a tsv from librarything"""

import re
from typing import Optional

from bookwyrm.models import Shelf

from . import Importer


def _remove_brackets(value: Optional[str]) -> Optional[str]:
    return re.sub(r"\[|\]", "", value) if value else None


class LibrarythingImporter(Importer):
    """csv downloads from librarything"""

    service = "LibraryThing"
    delimiter = "\t"
    encoding = "ISO-8859-1"

    # LibraryThing uses "Collections" column instead of "shelf"
    row_mappings_guesses = [
        ("id", ["id", "book id"]),
        ("title", ["title"]),
        ("authors", ["author_text", "author", "authors", "primary author"]),
        ("isbn_10", ["isbn_10", "isbn10", "isbn", "isbn/uid"]),
        ("isbn_13", ["isbn_13", "isbn13", "isbn", "isbns", "isbn/uid"]),
        ("shelf", ["shelf", "exclusive shelf", "read status", "bookshelf", "collections"]),
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

    def normalize_row(
        self, entry: dict[str, str], mappings: dict[str, Optional[str]]
    ) -> dict[str, Optional[str]]:
        """use the dataclass to create the formatted row of data"""
        normalized = {
            k: _remove_brackets(entry.get(v) if v else None)
            for k, v in mappings.items()
        }
        isbn_13 = value.split(", ") if (value := normalized.get("isbn_13")) else []
        normalized["isbn_13"] = isbn_13[1] if len(isbn_13) > 1 else None
        return normalized

    def get_shelf(self, normalized_row: dict[str, Optional[str]]) -> Optional[str]:
        # First check dates for accurate status
        if normalized_row["date_finished"]:
            return Shelf.READ_FINISHED
        if normalized_row["date_started"]:
            return Shelf.READING
        # Fall back to Collections/shelf field
        shelf_name = normalized_row.get("shelf")
        if shelf_name:
            shelf_name_lower = shelf_name.lower().strip()
            for shelf_key, guesses in self.shelf_mapping_guesses.items():
                if any(g in shelf_name_lower for g in guesses):
                    return shelf_key
        return Shelf.TO_READ
