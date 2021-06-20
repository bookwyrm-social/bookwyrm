""" handle reading a list of ISBN """
import re
import math

from . import Importer


class IsbnImporter(Importer):
    """list of downloads from ISBN"""

    service = "ISBN"
    # mandatory_fields : fields matching the book ISBN13
    mandatory_fields = ["ISBN13"]

    def parse_fields(self, entry, default_shelf):
        """custom parsing for ISBN"""
        data = {}
        data["import_source"] = self.service
        data["ISBN13"] = entry
        data["Exclusive Shelf"] = default_shelf
        data["Title"] = ""
        data["Author"] = ""
        data["My Review"] = ""
        data["My Rating"] = ""
        data["Date Added"] = None
        data["Date Started"] = None
        data["Date Read"] = None

        return data
