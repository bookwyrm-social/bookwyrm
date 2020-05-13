from django.test import TestCase

from fedireads import books_manager, models
from fedireads.connectors.fedireads_connector import Connector
from fedireads.settings import DOMAIN


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


    def test_get_by_absolute_id_local(self):
        abs_id = 'https://%s/book/%d' % (DOMAIN, self.work.id)
        work = books_manager.get_by_absolute_id(abs_id, models.Work)
        self.assertEqual(work, self.work)

        work = books_manager.get_by_absolute_id(abs_id, models.Edition)
        self.assertIsNone(work)


    def test_get_by_absolute_id_remote(self):
        remote_work = models.Work.objects.create(
            title='Example Work',
            remote_id='https://example.com/book/123',
        )

        abs_id = 'https://example.com/book/123'
        work = books_manager.get_by_absolute_id(abs_id, models.Work)
        self.assertEqual(work, remote_work)


    def test_get_by_absolute_id_invalid(self):
        abs_id = 'https://%s/book/34534623' % DOMAIN
        result = books_manager.get_by_absolute_id(abs_id, models.Work)
        self.assertIsNone(result)

        abs_id = 'httook534623'
        result = books_manager.get_by_absolute_id(abs_id, models.Work)
        self.assertIsNone(result)
