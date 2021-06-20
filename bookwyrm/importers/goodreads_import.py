""" handle reading a csv from goodreads """
from . import Importer


class GoodreadsImporter(Importer):
    """GoodReads is the default importer, thus Importer follows its structure.
    For a more complete example of overriding see librarything_import.py"""

    service = "GoodReads"

    def parse_fields(self, entry, default_shelf=None):
        """handle the specific fields in goodreads csvs"""
        entry.update({"import_source": self.service})
        # add missing 'Date Started' field
        entry.update({"Date Started": None})
        # add the option to override the shelf for all imported books
        if default_shelf:
            entry.update({"Exclusive Shelf": default_shelf})
        return entry
