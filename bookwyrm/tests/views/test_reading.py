''' test for app action functionality '''
from unittest.mock import patch
import dateutil
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils import timezone

from bookwyrm import models, views

class ReadingViews(TestCase):
    ''' viewing and creating statuses '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.com', 'mouseword',
            local=True, localname='mouse',
            remote_id='https://example.com/users/mouse',
        )
        self.work = models.Work.objects.create(title='Test Work')
        self.book = models.Edition.objects.create(
            title='Test Book',
            remote_id='https://example.com/book/1',
            parent_work=self.work
        )
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )

    def test_edit_readthrough(self):
        ''' adding dates to an ongoing readthrough '''
        start = timezone.make_aware(dateutil.parser.parse('2021-01-03'))
        readthrough = models.ReadThrough.objects.create(
            book=self.book, user=self.local_user, start_date=start)
        request = self.factory.post(
            '', {
                'start_date': '2017-01-01',
                'finish_date': '2018-03-07',
                'book': '',
                'id': readthrough.id,
            })
        request.user = self.local_user

        views.edit_readthrough(request)
        readthrough.refresh_from_db()
        self.assertEqual(readthrough.start_date.year, 2017)
        self.assertEqual(readthrough.start_date.month, 1)
        self.assertEqual(readthrough.start_date.day, 1)
        self.assertEqual(readthrough.finish_date.year, 2018)
        self.assertEqual(readthrough.finish_date.month, 3)
        self.assertEqual(readthrough.finish_date.day, 7)
        self.assertEqual(readthrough.book, self.book)


    def test_delete_readthrough(self):
        ''' remove a readthrough '''
        readthrough = models.ReadThrough.objects.create(
            book=self.book, user=self.local_user)
        models.ReadThrough.objects.create(
            book=self.book, user=self.local_user)
        request = self.factory.post(
            '', {
                'id': readthrough.id,
            })
        request.user = self.local_user

        views.delete_readthrough(request)
        self.assertFalse(
            models.ReadThrough.objects.filter(id=readthrough.id).exists())


    def test_create_readthrough(self):
        ''' adding new read dates '''
        request = self.factory.post(
            '', {
                'start_date': '2017-01-01',
                'finish_date': '2018-03-07',
                'book': self.book.id,
                'id': '',
            })
        request.user = self.local_user

        views.create_readthrough(request)
        readthrough = models.ReadThrough.objects.get()
        self.assertEqual(readthrough.start_date.year, 2017)
        self.assertEqual(readthrough.start_date.month, 1)
        self.assertEqual(readthrough.start_date.day, 1)
        self.assertEqual(readthrough.finish_date.year, 2018)
        self.assertEqual(readthrough.finish_date.month, 3)
        self.assertEqual(readthrough.finish_date.day, 7)
        self.assertEqual(readthrough.book, self.book)
        self.assertEqual(readthrough.user, self.local_user)
