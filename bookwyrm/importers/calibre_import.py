""" handle reading a csv from calibre """
from bookwyrm.models import Shelf

from . import Importer


class CalibreImporter(Importer):
    """csv downloads from Calibre"""

    service = "Calibre"

    def __init__(self, *args, **kwargs):
        # Add timestamp to row_mappings_guesses for date_added to avoid
        # integrity error
        row_mappings_guesses = []

        for field, mapping in self.row_mappings_guesses:
            if field in ("date_added",):
                row_mappings_guesses.append((field, mapping + ["timestamp"]))
            else:
                row_mappings_guesses.append((field, mapping))

        self.row_mappings_guesses = row_mappings_guesses
        super().__init__(*args, **kwargs)

    def get_shelf(self, normalized_row):
        # Calibre export does not indicate which shelf to use. Go with a default one for now
        return Shelf.TO_READ
