""" handle reading a csv from librarything """
import csv
import re
import math

from bookwyrm import models
from bookwyrm.models import ImportItem
from bookwyrm.importer import Importer


class LibrarythingImporter(Importer):
    service = "LibraryThing"
    delimiter = "\t"
    encoding = "ISO-8859-1"
    # mandatory_fields : fields matching the book title and author
    mandatory_fields = ["Title", "Primary Author"]

    def parse_fields(self, initial):
        data = {}
        data["import_source"] = self.service
        data["Book Id"] = initial["Book Id"]
        data["Title"] = initial["Title"]
        data["Author"] = initial["Primary Author"]
        data["ISBN13"] = initial["ISBN"]
        data["My Review"] = initial["Review"]
        if initial["Rating"]:
            data["My Rating"] = math.ceil(float(initial["Rating"]))
        else:
            data["My Rating"] = ""
        data["Date Added"] = re.sub("\[|\]", "", initial["Entry Date"])
        data["Date Started"] = re.sub("\[|\]", "", initial["Date Started"])
        data["Date Read"] = re.sub("\[|\]", "", initial["Date Read"])

        data["Exclusive Shelf"] = None
        if data["Date Read"]:
            data["Exclusive Shelf"] = "read"
        elif data["Date Started"]:
            data["Exclusive Shelf"] = "reading"
        else:
            data["Exclusive Shelf"] = "to-read"

        return data
