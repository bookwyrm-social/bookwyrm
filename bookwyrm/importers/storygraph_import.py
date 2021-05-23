""" handle reading a csv from librarything """
import re
import math

from . import Importer


class StorygraphImporter(Importer):
    """csv downloads from librarything"""

    service = "Storygraph"
    # mandatory_fields : fields matching the book title and author
    mandatory_fields = ["Title"]

    def parse_fields(self, entry):
        """custom parsing for storygraph"""
        data = {}
        data["import_source"] = self.service
        data["Title"] = entry["Title"]
        data["Author"] = entry["Authors"] if "Authors" in entry else entry["Author"]
        data["ISBN13"] = entry["ISBN"]
        data["My Review"] = entry["Review"]
        if entry["Star Rating"]:
            data["My Rating"] = math.ceil(float(entry["Star Rating"]))
        else:
            data["My Rating"] = ""

        data["Date Added"] = re.sub(r"[/]", "-", entry["Date Added"])
        data["Date Read"] = re.sub(r"[/]", "-", entry["Last Date Read"])

        data["Exclusive Shelf"] = (
            {"read": "read", "currently-reading": "reading", "to-read": "to-read"}
        ).get(entry["Read Status"], None)
        return data
