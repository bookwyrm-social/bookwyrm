"""test adding/removing libris connector"""

from django.test import TestCase

from bookwyrm.management.commands import add_libris_connector
from bookwyrm.models import Connector


class InitDB(TestCase):
    """add/remove libris connector"""

    def test_adding_connector(self):
        add_libris_connector.enable_libris_connector()
        self.assertTrue(
            Connector.objects.filter(identifier="libris.kb.se", active=True).exists()
        )

    def test_command_no_args(self):
        command = add_libris_connector.Command()
        command.handle()
        self.assertTrue(
            Connector.objects.filter(identifier="libris.kb.se", active=True).exists()
        )

    def test_command_with_args(self):
        command = add_libris_connector.Command()
        command.handle(deactivate=True)
        self.assertFalse(
            Connector.objects.filter(identifier="libris.kb.se", active=True).exists()
        )
