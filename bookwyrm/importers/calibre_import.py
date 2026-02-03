"""handle reading a csv from calibre"""

from typing import Any, Optional

from bookwyrm.models import Shelf

from . import Importer


class CalibreImporter(Importer):
    """csv downloads from Calibre"""

    service = "Calibre"

    def __init__(self, *args: Any, **kwargs: Any):
        # Add timestamp to row_mappings_guesses for date_added to avoid
        # integrity error
        self.row_mappings_guesses = [
            (field, mapping + (["timestamp"] if field == "date_added" else []))
            for field, mapping in self.row_mappings_guesses
        ]
        super().__init__(*args, **kwargs)

    def get_shelf(self, normalized_row: dict[str, Optional[str]]) -> Optional[str]:
        # Calibre export does not indicate which shelf to use. Use a default one for now
        return Shelf.TO_READ
