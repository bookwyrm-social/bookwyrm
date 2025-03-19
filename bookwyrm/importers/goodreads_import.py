""" handle reading a csv from goodreads """
from typing import Optional
from . import Importer


class GoodreadsImporter(Importer):
    """Goodreads is the default importer, thus Importer follows its structure.
    For a more complete example of overriding see librarything_import.py"""

    service = "Goodreads"

    def normalize_row(
        self, entry: dict[str, str], mappings: dict[str, Optional[str]]
    ) -> dict[str, Optional[str]]:
        normalized = super().normalize_row(entry, mappings)
        normalized["goodreads_key"] = normalized["id"]
        return normalized
