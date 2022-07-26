""" Get your admin code to allow install """
from django.core.management.base import BaseCommand

from bookwyrm import models
from bookwyrm.settings import VERSION


# pylint: disable=no-self-use
class Command(BaseCommand):
    """command-line options"""

    help = "What version is this?"

    def add_arguments(self, parser):
        """specify which function to run"""
        parser.add_argument(
            "--current",
            action="store_true",
            help="Version stored in database",
        )
        parser.add_argument(
            "--target",
            action="store_true",
            help="Version stored in settings",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update database version",
        )

    # pylint: disable=unused-argument
    def handle(self, *args, **options):
        """execute init"""
        site = models.SiteSettings.objects.get()
        current = site.version or "0.0.1"
        target = VERSION
        if options.get("current"):
            print(current)
            return

        if options.get("target"):
            print(target)
            return

        if options.get("update"):
            site.version = target
            site.save()
            return

        if current != target:
            print(f"{current}/{target}")
        else:
            print(current)
