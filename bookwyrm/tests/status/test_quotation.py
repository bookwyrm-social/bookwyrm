from django.test import TestCase
import json
import pathlib

from fedireads import activitypub, models
from fedireads import status as status_builder


class Quotation(TestCase):
    ''' we have hecka ways to create statuses '''
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword',
            remote_id='https://example.com/user/mouse'
        )
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
        )


    def test_create_quotation(self):
        quotation = status_builder.create_quotation(
            self.user, self.book, 'commentary', 'a quote')
        self.assertEqual(quotation.quote, 'a quote')
        self.assertEqual(quotation.content, 'commentary')
