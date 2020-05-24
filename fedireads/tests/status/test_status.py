from django.test import TestCase

from fedireads import models
from fedireads import status as status_builder


class Status(TestCase):
    ''' we have hecka ways to create statuses '''
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword',
            local=False,
            inbox='https://example.com/user/mouse/inbox',
            outbox='https://example.com/user/mouse/outbox',
            remote_id='https://example.com/user/mouse'
        )


    def test_create_status(self):
        content = 'statuses are usually <i>replies</i>'
        status = status_builder.create_status(
            self.user, content)
        self.assertEqual(status.content, content)

        reply = status_builder.create_status(
            self.user, content, reply_parent=status)
        self.assertEqual(reply.content, content)
        self.assertEqual(reply.reply_parent, status)


    def test_create_status_from_activity(self):
        book = models.Edition.objects.create(title='Example Edition')
        review = status_builder.create_review(
            self.user, book, 'review name', 'content', 5)
        activity = {
            'id': 'https://example.com/user/mouse/status/12',
            'url': 'https://example.com/user/mouse/status/12',
            'inReplyTo': review.remote_id,
            'published': '2020-05-10T02:15:59.635557+00:00',
            'attributedTo': 'https://example.com/user/mouse',
            'to': [
                'https://www.w3.org/ns/activitystreams#Public'
                ],
            'cc': [
                'https://example.com/user/mouse/followers'
                ],
            'sensitive': False,
            'content': 'reply to status',
            'type': 'Note',
            'attachment': [],
            'replies': {
                'id': 'https://example.com/user/mouse/status/12/replies',
                'type': 'Collection',
                'first': {
                    'type': 'CollectionPage',
                    'next': 'https://example.com/user/mouse/status/12/replies?only_other_accounts=true&page=true',
                    'partOf': 'https://example.com/user/mouse/status/12/replies',
                    'items': []
                    }
                }
            }

        status = status_builder.create_status_from_activity(
            self.user, activity)
        self.assertEqual(status.reply_parent, review)
        self.assertEqual(status.content, 'reply to status')
        self.assertEqual(
            status.published_date,
            '2020-05-10T02:15:59.635557+00:00'
        )
