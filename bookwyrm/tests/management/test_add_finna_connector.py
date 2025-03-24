""" test populating user streams """
from django.test import TestCase

from bookwyrm.models import Connector
from bookwyrm.management.commands import add_finna_connector


class InitDB(TestCase):
    """Add/remove finna connector"""

    def test_adding_connector(self):
        """Create groups"""
        add_finna_connector.enable_finna_connector()
        self.assertTrue(
            Connector.objects.filter(identifier="api.finna.fi", active=True).exists()
        )

    def test_command_no_args(self):
        """command line calls"""
        command = add_finna_connector.Command()
        command.handle()
        self.assertTrue(
            Connector.objects.filter(identifier="api.finna.fi", active=True).exists()
        )

    def test_command_with_args(self):
        """command line calls"""
        command = add_finna_connector.Command()
        command.handle(deactivate=True)

        # everything should have been cleaned
        self.assertFalse(
            Connector.objects.filter(identifier="api.finna.fi", active=True).exists()
        )
