""" handle reading a csv from goodreads """
from bookwyrm.importer import Importer

# GoodReads is the default importer, thus Importer follows its structure. For a more complete example of overriding see librarything_import.py


class GoodreadsImporter(Importer):
    service = "GoodReads"

    def parse_fields(self, data):
        data.update({"import_source": self.service})
        # add missing 'Date Started' field
        data.update({"Date Started": None})
        return data
