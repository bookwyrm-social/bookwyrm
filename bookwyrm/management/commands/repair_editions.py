""" Repair editions with missing works """
from django.core.management.base import BaseCommand
from bookwyrm import models


class Command(BaseCommand):
    """command-line options"""

    help = "Repairs an edition that is in a broken state"

    # pylint: disable=unused-argument
    def handle(self, *args, **options):
        """Find and repair broken editions"""
        # Find broken editions
        editions = models.Edition.objects.filter(parent_work__isnull=True)
        self.stdout.write(f"Repairing {editions.count()} edition(s):")

        # Do repair
        for edition in editions:
            edition.repair()
            self.stdout.write(".", ending="")
