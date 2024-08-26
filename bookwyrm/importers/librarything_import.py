""" handle reading a tsv from librarything """
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
        if normalized_row["date_finished"]:
            return Shelf.READ_FINISHED
        if normalized_row["date_started"]:
            return Shelf.READING
        return Shelf.TO_READ
