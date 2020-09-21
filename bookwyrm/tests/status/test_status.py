from django.test import TestCase

from bookwyrm import models
from bookwyrm import status as status_builder


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
