""" handle reading a csv from calibre """
from typing import Any, Optional

from bookwyrm.models import Shelf

from . import Importer


class CalibreImporter(Importer):
    """csv downloads from Calibre"""

    service = "Calibre"

    def __init__(self, *args: Any, **kwargs: Any):
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

    def get_shelf(self, normalized_row: dict[str, Optional[str]]) -> Optional[str]:
        # Calibre export does not indicate which shelf to use. Use a default one for now
        return Shelf.TO_READ
