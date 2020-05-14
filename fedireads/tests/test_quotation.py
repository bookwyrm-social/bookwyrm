from django.test import TestCase

from fedireads import models
from fedireads import status as status_builder


class Quotation(TestCase):
    ''' we have hecka ways to create statuses '''
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')
        self.book = models.Edition.objects.create(title='Example Edition')


    def test_create_quotation(self):
        quotation = status_builder.create_quotation(
            self.user, self.book, 'commentary', 'a quote')
        self.assertEqual(quotation.quote, 'a quote')
        self.assertEqual(quotation.content, 'commentary')


    def test_quotation_from_activity(self):
        activity = {
            'id': 'https://example.com/user/mouse/quotation/13',
            'url': 'https://example.com/user/mouse/quotation/13',
            'inReplyTo': None,
            'published': '2020-05-10T02:38:31.150343+00:00',
            'attributedTo': 'https://example.com/user/mouse',
            'to': [
                'https://www.w3.org/ns/activitystreams#Public'
                ],
            'cc': [
                'https://example.com/user/mouse/followers'
                ],
            'sensitive': False,
            'content': 'commentary',
            'type': 'Note',
            'attachment': [
                {
                    'type': 'Document',
                    'mediaType': 'image//images/covers/2b4e4712-5a4d-4ac1-9df4-634cc9c7aff3jpg',
                    'url': 'https://example.com/images/covers/2b4e4712-5a4d-4ac1-9df4-634cc9c7aff3jpg',
                    'name': 'Cover of \'This Is How You Lose the Time War\''
                    }
                ],
            'replies': {
                'id': 'https://example.com/user/mouse/quotation/13/replies',
                'type': 'Collection',
                'first': {
                    'type': 'CollectionPage',
                    'next': 'https://example.com/user/mouse/quotation/13/replies?only_other_accounts=true&page=true',
                    'partOf': 'https://example.com/user/mouse/quotation/13/replies',
                    'items': []
                    }
                },
            'inReplyToBook': self.book.remote_id,
            'fedireadsType': 'Quotation',
            'quote': 'quote body'
        }
        quotation = status_builder.create_quotation_from_activity(
            self.user, activity)
        self.assertEqual(quotation.content, 'commentary')
        self.assertEqual(quotation.quote, 'quote body')
        self.assertEqual(quotation.book, self.book)
        self.assertEqual(
            quotation.published_date, '2020-05-10T02:38:31.150343+00:00')
