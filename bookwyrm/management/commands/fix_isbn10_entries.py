from django.core.management.base import BaseCommand
from django.db.models.functions import Length
from bookwyrm import models


def find_long_isbn10_editions():
    """Fix isbn-10 entries that have incorrect checksum"""
    entries_to_fix = (
        models.Edition.objects.annotate(isbn10_length=Length("isbn_10"))
        .filter(isbn10_length__gt=10)
        .filter(isbn_10__endswith="11")
    )

    print(f"{entries_to_fix.count()} editions to find")

    for edition_to_fix in entries_to_fix:
        edition_to_fix.isbn_10 = edition_to_fix.isbn_10[:9] + "0"
        edition_to_fix.save(broadcast=True, update_fields=["isbn_10"])


class Command(BaseCommand):
    """Fix isbn-10 entries that have incorrect checksum"""

    help = "Find and fix isbn-10 entries that have incorrect checksum"

    def handle(self, *args, **options):
        """run fix"""
        find_long_isbn10_editions()
