"""handle reading a csv from openreads"""

from typing import Optional
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

    row_mappings_guesses = Importer.row_mappings_guesses + [
        ("openlibrary_key", ["olid"]),
        ("pages", ["pages"]),
        ("description", ["description"]),
        ("physical_format", ["book_format"]),
        ("published_date", ["publication_year"]),
    ]

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
        # no reading dates: fall back to the "shelf" column
        return super().get_shelf(normalized_row) or Shelf.TO_READ
