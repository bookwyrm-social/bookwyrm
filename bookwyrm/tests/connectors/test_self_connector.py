''' testing book data connectors '''
import datetime
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models
from bookwyrm.connectors.self_connector import Connector
from bookwyrm.settings import DOMAIN


class SelfConnector(TestCase):
    def setUp(self):
        models.Connector.objects.create(
            identifier=DOMAIN,
            name='Local',
            local=True,
            connector_file='self_connector',
            base_url='https://%s' % DOMAIN,
            books_url='https://%s/book' % DOMAIN,
            covers_url='https://%s/images/covers' % DOMAIN,
            search_url='https://%s/search?q=' % DOMAIN,
            priority=1,
        )
        self.connector = Connector(DOMAIN)
        self.work = models.Work.objects.create(
            title='Example Work',
        )
        self.edition = models.Edition.objects.create(
            title='Edition of Example Work',
            author_text='Anonymous',
            published_date=datetime.datetime(1980, 5, 10, tzinfo=timezone.utc),
            parent_work=self.work,
        )
        models.Edition.objects.create(
            title='Another Edition',
            parent_work=self.work,
            series='Anonymous'
        )
        models.Edition.objects.create(
            title='More Editions',
            subtitle='The Anonymous Edition',
            parent_work=self.work,
        )
        models.Edition.objects.create(
            title='An Edition',
            author_text='Fish',
            parent_work=self.work
        )


    def test_format_search_result(self):
        result = self.connector.search('Edition of Example')[0]
        self.assertEqual(result.title, 'Edition of Example Work')
        self.assertEqual(result.key, self.edition.remote_id)
        self.assertEqual(result.author, 'Anonymous')
        self.assertEqual(result.year, 1980)


    def test_search_rank(self):
        results = self.connector.search('Anonymous')
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, 'More Editions')
        self.assertEqual(results[1].title, 'Edition of Example Work')


    def test_search_default_filter(self):
        ''' it should get rid of duplicate editions for the same work '''
        self.work.default_edition = self.edition
        self.work.save()

        results = self.connector.search('Anonymous')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'Edition of Example Work')

        results = self.connector.search('Fish')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'An Edition')
