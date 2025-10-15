""" handle reading a csv from openreads"""
from typing import Any, Optional
from datetime import datetime
from bookwyrm.models import Shelf

from . import Importer


def parse_iso_timestamp(iso_date: str | None) -> None | str:
    """Parse iso timestamp and return iso-formated date"""
    if not iso_date:
        return iso_date
    return datetime.fromisoformat(iso_date).date().isoformat()


class OpenReadsImporter(Importer):
    """csv downloads from OpenLibrary"""

    service = "OpenReads"

    def __init__(self, *args: Any, **kwargs: Any):
        self.row_mappings_guesses.append(("openlibrary_key", ["olid"]))
        self.row_mappings_guesses.append(("pages", ["pages"]))
        self.row_mappings_guesses.append(("description", ["description"]))
        self.row_mappings_guesses.append(("physical_format", ["book_format"]))
        self.row_mappings_guesses.append(("published_date", ["publication_year"]))
        super().__init__(*args, **kwargs)

    def normalize_row(
        self, entry: dict[str, str], mappings: dict[str, Optional[str]]
    ) -> dict[str, Optional[str]]:
        normalized = {k: entry.get(v) if v else None for k, v in mappings.items()}

        reading_list = value.split(";") if (value := entry.get("readings")) else []
        if reading_list:
            if reading_dates := reading_list[0].split("|"):
                normalized["date_started"] = (
                    parse_iso_timestamp(reading_dates[0]) or None
                )
                normalized["date_finished"] = (
                    parse_iso_timestamp(reading_dates[1]) or None
                )
        if date_added := normalized.get("date_added"):
            normalized["date_added"] = parse_iso_timestamp(date_added)
        if read_status := entry.get("status"):
            match read_status:
                case "finished":
                    normalized["shelf"] = Shelf.READ_FINISHED
                case "in_progress":
                    normalized["shelf"] = Shelf.READING
                case "abandoned":
                    normalized["shelf"] = Shelf.STOPPED_READING
        return normalized

    def get_shelf(self, normalized_row: dict[str, Optional[str]]) -> Optional[str]:
        if normalized_row["date_finished"]:
            return Shelf.READ_FINISHED
        if normalized_row["date_started"]:
            return Shelf.READING
        return Shelf.TO_READ
