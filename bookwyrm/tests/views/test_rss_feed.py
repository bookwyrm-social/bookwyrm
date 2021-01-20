''' testing import '''

from unittest.mock import patch

from django.test import RequestFactory, TestCase
import responses

from bookwyrm import models
from bookwyrm.views import rss_feed
from bookwyrm.settings import DOMAIN

class RssFeed(TestCase):
    ''' rss feed behaves as expected '''
    def setUp(self):
        self.user = models.User.objects.create_user(
            'rss_user', 'rss@test.rss', 'password', local=True)

        work = models.Work.objects.create(title='Test Work')
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
            parent_work=work
        )

        self.review = models.Review.objects.create(
            name='Review name', content='test content', rating=3,
            user=self.user, book=self.book)

        self.quote = models.Quotation.objects.create(
            quote='a sickening sense', content='test content',
            user=self.user, book=self.book)
        
        self.generatednote = models.GeneratedNote.objects.create(
            content='test content', user=self.user)

        self.factory = RequestFactory()
        

    def test_rss_feed(self):
        request = self.factory.get('/user/rss_user/rss')
        response = RssFeed(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(False, True)

