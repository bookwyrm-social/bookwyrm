from django.test import TestCase

from bookwyrm import models
from bookwyrm.connectors import connector_manager
from bookwyrm.connectors.bookwyrm_connector import Connector as BookWyrmConnector
from bookwyrm.connectors.self_connector import Connector as SelfConnector


class ConnectorManager(TestCase):
    def setUp(self):
        self.work = models.Work.objects.create(
            title='Example Work'
        )

        self.edition = models.Edition.objects.create(
            title='Example Edition',
            parent_work=self.work
        )
        self.work.default_edition = self.edition
        self.work.save()

        self.connector = models.Connector.objects.create(
            identifier='test_connector',
            priority=1,
            local=True,
            connector_file='self_connector',
            base_url='http://test.com/',
            books_url='http://test.com/',
            covers_url='http://test.com/',
        )

    def test_get_edition(self):
        edition = connector_manager.get_edition(self.edition.id)
        self.assertEqual(edition, self.edition)


    def test_get_edition_work(self):
        edition = connector_manager.get_edition(self.work.id)
        self.assertEqual(edition, self.edition)


    def test_get_or_create_connector(self):
        remote_id = 'https://example.com/object/1'
        connector = connector_manager.get_or_create_connector(remote_id)
        self.assertIsInstance(connector, BookWyrmConnector)
        self.assertEqual(connector.identifier, 'example.com')
        self.assertEqual(connector.base_url, 'https://example.com')

        same_connector = connector_manager.get_or_create_connector(remote_id)
        self.assertEqual(connector.identifier, same_connector.identifier)

    def test_get_connectors(self):
        remote_id = 'https://example.com/object/1'
        connector_manager.get_or_create_connector(remote_id)
        connectors = list(connector_manager.get_connectors())
        self.assertEqual(len(connectors), 2)
        self.assertIsInstance(connectors[0], SelfConnector)
        self.assertIsInstance(connectors[1], BookWyrmConnector)

    def test_search(self):
        results = connector_manager.search('Example')
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0]['connector'], SelfConnector)
        self.assertEqual(len(results[0]['results']), 1)
        self.assertEqual(results[0]['results'][0].title, 'Example Edition')

    def test_local_search(self):
        results = connector_manager.local_search('Example')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'Example Edition')

    def test_first_search_result(self):
        result = connector_manager.first_search_result('Example')
        self.assertEqual(result.title, 'Example Edition')
        no_result = connector_manager.first_search_result('dkjfhg')
        self.assertIsNone(no_result)

    def test_load_connector(self):
        connector = connector_manager.load_connector(self.connector)
        self.assertIsInstance(connector, SelfConnector)
        self.assertEqual(connector.identifier, 'test_connector')
