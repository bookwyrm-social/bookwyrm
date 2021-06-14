""" interface between the app and various connectors """
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors import connector_manager
from bookwyrm.connectors.bookwyrm_connector import Connector as BookWyrmConnector
from bookwyrm.connectors.self_connector import Connector as SelfConnector


class ConnectorManager(TestCase):
    """interface between the app and various connectors"""

    def setUp(self):
        """we'll need some books and a connector info entry"""
        self.work = models.Work.objects.create(title="Example Work")

        self.edition = models.Edition.objects.create(
            title="Example Edition", parent_work=self.work, isbn_10="0000000000"
        )
        self.edition = models.Edition.objects.create(
            title="Another Edition", parent_work=self.work, isbn_10="1111111111"
        )

        self.connector = models.Connector.objects.create(
            identifier="test_connector",
            priority=1,
            local=True,
            connector_file="self_connector",
            base_url="http://test.com/",
            books_url="http://test.com/",
            covers_url="http://test.com/",
            isbn_search_url="http://test.com/isbn/",
        )

        self.remote_connector = models.Connector.objects.create(
            identifier="test_connector_remote",
            priority=1,
            local=False,
            connector_file="bookwyrm_connector",
            base_url="http://fake.ciom/",
            books_url="http://fake.ciom/",
            search_url="http://fake.ciom/search/",
            covers_url="http://covers.fake.ciom/",
            isbn_search_url="http://fake.ciom/isbn/",
        )

    def test_get_or_create_connector(self):
        """loads a connector if the data source is known or creates one"""
        remote_id = "https://example.com/object/1"
        connector = connector_manager.get_or_create_connector(remote_id)
        self.assertIsInstance(connector, BookWyrmConnector)
        self.assertEqual(connector.identifier, "example.com")
        self.assertEqual(connector.base_url, "https://example.com")

        same_connector = connector_manager.get_or_create_connector(remote_id)
        self.assertEqual(connector.identifier, same_connector.identifier)

    def test_get_connectors(self):
        """load all connectors"""
        connectors = list(connector_manager.get_connectors())
        self.assertEqual(len(connectors), 2)
        self.assertIsInstance(connectors[0], SelfConnector)
        self.assertIsInstance(connectors[1], BookWyrmConnector)

    @responses.activate
    def test_search(self):
        """search all connectors"""
        responses.add(
            responses.GET,
            "http://fake.ciom/search/Example?min_confidence=0.1",
            json={},
        )
        results = connector_manager.search("Example")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0]["connector"], SelfConnector)
        self.assertEqual(len(results[0]["results"]), 1)
        self.assertEqual(results[0]["results"][0].title, "Example Edition")

    def test_search_empty_query(self):
        """don't panic on empty queries"""
        results = connector_manager.search("")
        self.assertEqual(results, [])

    @responses.activate
    def test_search_isbn(self):
        """special handling if a query resembles an isbn"""
        responses.add(
            responses.GET,
            "http://fake.ciom/isbn/0000000000",
            json={},
        )
        results = connector_manager.search("0000000000")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0]["connector"], SelfConnector)
        self.assertEqual(len(results[0]["results"]), 1)
        self.assertEqual(results[0]["results"][0].title, "Example Edition")

    def test_local_search(self):
        """search only the local database"""
        results = connector_manager.local_search("Example")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Example Edition")

    def test_first_search_result(self):
        """only get one search result"""
        result = connector_manager.first_search_result("Example")
        self.assertEqual(result.title, "Example Edition")

    def test_first_search_result_empty_query(self):
        """only get one search result"""
        result = connector_manager.first_search_result("")
        self.assertIsNone(result)

    @responses.activate
    def test_first_search_result_no_results(self):
        """only get one search result"""
        responses.add(
            responses.GET,
            "http://fake.ciom/search/dkjfhg?min_confidence=0.1",
            json={},
        )
        result = connector_manager.first_search_result("dkjfhg")
        self.assertIsNone(result)

    def test_load_connector(self):
        """load a connector object from the database entry"""
        connector = connector_manager.load_connector(self.connector)
        self.assertIsInstance(connector, SelfConnector)
        self.assertEqual(connector.identifier, "test_connector")
