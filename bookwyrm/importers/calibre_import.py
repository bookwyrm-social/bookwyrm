""" handle reading a csv from calibre """
from bookwyrm.models import Shelf

from . import Importer


class CalibreImporter(Importer):
    """csv downloads from Calibre"""

    service = "Calibre"

    def get_shelf(self, normalized_row):
        # Calibre export does not indicate which shelf to use. Go with a default one for now
        return Shelf.TO_READ
