""" handle reading a tsv from librarything """
import re
from . import Importer


class LibrarythingImporter(Importer):
    """csv downloads from librarything"""

    service = "LibraryThing"
    delimiter = "\t"
    encoding = "ISO-8859-1"

    def normalize_row(self, entry, mappings):  # pylint: disable=no-self-use
        """use the dataclass to create the formatted row of data"""
        normalized = {k: entry.get(v) for k, v in mappings.items()}
        for date_field in self.date_fields:
            date = normalized[date_field]
            normalized[date_field] = re.sub(r"\[|\]", "", date)
        return normalized

    def get_shelf(self, normalized_row):
        if normalized_row["date_finished"]:
            return "read"
        if normalized_row["date_started"]:
            return "reading"
        return "to-read"
