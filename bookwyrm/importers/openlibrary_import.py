"""handle reading a csv from openlibrary"""

from . import Importer


class OpenLibraryImporter(Importer):
    """csv downloads from OpenLibrary"""

    service = "OpenLibrary"

    row_mappings_guesses = Importer.row_mappings_guesses + [
        ("openlibrary_key", ["edition id"]),
        ("openlibrary_work_key", ["work id"]),
    ]
