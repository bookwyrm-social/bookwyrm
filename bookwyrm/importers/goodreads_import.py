""" handle reading a csv from goodreads """
from . import Importer


class GoodreadsImporter(Importer):
    """Goodreads is the default importer, thus Importer follows its structure.
    For a more complete example of overriding see librarything_import.py"""

    service = "Goodreads"
