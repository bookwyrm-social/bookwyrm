""" handle reading a csv from inventaire.io """
import re
import math

from . import Importer


class InventaireImporter(Importer):
    """csv downloads from inventaire.io"""

    service = "Inventaire.io"
    mandatory_fields = ["Edition ISBN-13"] #["Works URLs", "Works labels", "Authors labels", "Edition ISBN-13", "Item created"]

    def parse_fields(self, entry):
        """custom parsing for inventaire.io"""
        data = {}
        data["import_source"] = self.service
        data["Book Id"] = re.sub(r".*/", "", entry["Works URLs"])
        data["Title"] = entry["Works labels"]
        data["Author"] = entry["Authors labels"].split(',')[0]
        data["ISBN13"] = entry["Edition ISBN-13"]
        data["Date Added"] = entry["Item created"]
        # skip review entirely since Inventaire.io does not do reviews.
        data["My Review"] = None
        data["My Rating"] = None
        # No reading support either
        data["Date Started"] = None
        data["Date Read"] = None
        # Maybe put this in to-read by default?
        data["Exclusive Shelf"] = None

        return data

