""" handle reading a csv from openlibrary"""
from typing import Any

from . import Importer


class OpenLibraryImporter(Importer):
    """csv downloads from OpenLibrary"""

    service = "OpenLibrary"

    def __init__(self, *args: Any, **kwargs: Any):
        self.row_mappings_guesses.append(("openlibrary_key", ["edition id"]))
        self.row_mappings_guesses.append(("openlibrary_work_key", ["work id"]))
        super().__init__(*args, **kwargs)
