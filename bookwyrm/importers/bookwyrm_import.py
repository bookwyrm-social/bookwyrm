""" handle reading a csv from BookWyrm """

from typing import Any
from . import Importer


class BookwyrmBooksImporter(Importer):
    """Goodreads is the default importer, we basically just use the same structure"""

    service = "BookWyrm"

    def __init__(self, *args: Any, **kwargs: Any):
        self.row_mappings_guesses.append(("shelf_name", ["shelf_name"]))
        super().__init__(*args, **kwargs)
