""" Get your admin code to allow install """
from django.core.management.base import BaseCommand

from bookwyrm import models


def get_admin_code():
    """get that code"""
    return models.SiteSettings.objects.get().admin_code


class Command(BaseCommand):
    """command-line options"""

    help = "Gets admin code for configuring BookWyrm"

    # pylint: disable=unused-argument
    def handle(self, *args, **options):
        """execute init"""
        self.stdout.write("*******************************************")
        self.stdout.write("Use this code to create your admin account:")
        self.stdout.write(get_admin_code())
        self.stdout.write("*******************************************")
