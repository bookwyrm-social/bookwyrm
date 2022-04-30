""" handle reading a csv from calibre """
from . import Importer


class CalibreImporter(Importer):
    """csv downloads from OpenLibrary"""

    service = "Calibre"
