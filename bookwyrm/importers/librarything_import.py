""" handle reading a csv from librarything """
import re
import math

from . import Importer


class LibrarythingImporter(Importer):
    """csv downloads from librarything"""

    service = "LibraryThing"
    delimiter = "\t"
    encoding = "ISO-8859-1"
    # mandatory_fields : fields matching the book title and author
    mandatory_fields = ["Title", "Primary Author"]

    def parse_fields(self, entry):
        """custom parsing for librarything"""
        data = {}
        data["import_source"] = self.service
        data["Book Id"] = entry["Book Id"]
        data["Title"] = entry["Title"]
        data["Author"] = entry["Primary Author"]
        data["ISBN13"] = entry["ISBN"]
        data["My Review"] = entry["Review"]
        if entry["Rating"]:
            data["My Rating"] = math.ceil(float(entry["Rating"]))
        else:
            data["My Rating"] = ""
        data["Date Added"] = re.sub(r"\[|\]", "", entry["Entry Date"])
        data["Date Started"] = re.sub(r"\[|\]", "", entry["Date Started"])
        data["Date Read"] = re.sub(r"\[|\]", "", entry["Date Read"])

        data["Exclusive Shelf"] = None
        if data["Date Read"]:
            data["Exclusive Shelf"] = "read"
        elif data["Date Started"]:
            data["Exclusive Shelf"] = "reading"
        else:
            data["Exclusive Shelf"] = "to-read"

        return data
