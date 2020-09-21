from django.test import TestCase

from bookwyrm import books_manager, models
from bookwyrm.connectors.bookwyrm_connector import Connector
from bookwyrm.settings import DOMAIN


class Book(TestCase):
    def setUp(self):
        self.work = models.Work.objects.create(
            title='Example Work'
        )

        self.edition = models.Edition.objects.create(
            title='Example Edition',
            parent_work=self.work
        )

    def test_get_edition(self):
        edition = books_manager.get_edition(self.edition.id)
        self.assertEqual(edition, self.edition)


    def test_get_edition_work(self):
        edition = books_manager.get_edition(self.work.id)
        self.assertEqual(edition, self.edition)


    def test_get_or_create_connector(self):
        remote_id = 'https://example.com/object/1'
        connector = books_manager.get_or_create_connector(remote_id)
        self.assertIsInstance(connector, Connector)
        self.assertEqual(connector.identifier, 'example.com')
        self.assertEqual(connector.base_url, 'https://example.com')

        same_connector = books_manager.get_or_create_connector(remote_id)
        self.assertEqual(connector.identifier, same_connector.identifier)
