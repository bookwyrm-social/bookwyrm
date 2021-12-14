""" handle reading a csv from openlibrary"""
from . import Importer


class OpenLibraryImporter(Importer):
    """csv downloads from OpenLibrary"""

    service = "OpenLibrary"
