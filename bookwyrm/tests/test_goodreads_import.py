''' testing import '''
from collections import namedtuple
import pathlib
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import goodreads_import, models
from bookwyrm.settings import DOMAIN

class GoodreadsImport(TestCase):
    ''' importing from goodreads csv '''
    def setUp(self):
        ''' use a test csv '''
        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/goodreads.csv')
        self.csv = open(datafile, 'r')
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'password', local=True)

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


    def test_create_job(self):
        ''' creates the import job entry and checks csv '''
        import_job = goodreads_import.create_job(
            self.user, self.csv, False, 'public')
        self.assertEqual(import_job.user, self.user)
        self.assertEqual(import_job.include_reviews, False)
        self.assertEqual(import_job.privacy, 'public')

        import_items = models.ImportItem.objects.filter(job=import_job).all()
        self.assertEqual(len(import_items), 3)
        self.assertEqual(import_items[0].index, 0)
        self.assertEqual(import_items[0].data['Book Id'], '42036538')
        self.assertEqual(import_items[1].index, 1)
        self.assertEqual(import_items[1].data['Book Id'], '52691223')
        self.assertEqual(import_items[2].index, 2)
        self.assertEqual(import_items[2].data['Book Id'], '28694510')


    def test_create_retry_job(self):
        ''' trying again with items that didn't import '''
        import_job = goodreads_import.create_job(
            self.user, self.csv, False, 'unlisted')
        import_items = models.ImportItem.objects.filter(
            job=import_job
            ).all()[:2]

        retry = goodreads_import.create_retry_job(
            self.user, import_job, import_items)
        self.assertNotEqual(import_job, retry)
        self.assertEqual(retry.user, self.user)
        self.assertEqual(retry.include_reviews, False)
        self.assertEqual(retry.privacy, 'unlisted')

        retry_items = models.ImportItem.objects.filter(job=retry).all()
        self.assertEqual(len(retry_items), 2)
        self.assertEqual(retry_items[0].index, 0)
        self.assertEqual(retry_items[0].data['Book Id'], '42036538')
        self.assertEqual(retry_items[1].index, 1)
        self.assertEqual(retry_items[1].data['Book Id'], '52691223')


    def test_start_import(self):
        ''' begin loading books '''
        import_job = goodreads_import.create_job(
            self.user, self.csv, False, 'unlisted')
        MockTask = namedtuple('Task', ('id'))
        mock_task = MockTask(7)
        with patch('bookwyrm.goodreads_import.import_data.delay') as start:
            start.return_value = mock_task
            goodreads_import.start_import(import_job)
        import_job.refresh_from_db()
        self.assertEqual(import_job.task_id, '7')


    @responses.activate
    def test_import_data(self):
        ''' resolve entry '''
        import_job = goodreads_import.create_job(
            self.user, self.csv, False, 'unlisted')
        book = models.Edition.objects.create(title='Test Book')

        with patch(
                'bookwyrm.models.import_job.ImportItem.get_book_from_isbn'
                ) as resolve:
            resolve.return_value = book
            with patch('bookwyrm.outgoing.handle_imported_book'):
                goodreads_import.import_data(import_job.id)

        import_item = models.ImportItem.objects.get(job=import_job, index=0)
        self.assertEqual(import_item.book.id, book.id)
