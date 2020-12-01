from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, broadcast


class Book(TestCase):
    def setUp(self):
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)

        local_follower = models.User.objects.create_user(
            'joe', 'joe@mouse.mouse', 'jeoword', local=True)
        self.user.followers.add(local_follower)

        with patch('bookwyrm.models.user.set_remote_server.delay'):
            follower = models.User.objects.create_user(
                'rat', 'rat@mouse.mouse', 'ratword', local=False,
                remote_id='http://example.com/u/1',
                outbox='http://example.com/u/1/o',
                shared_inbox='http://example.com/inbox',
                inbox='http://example.com/u/1/inbox')
            self.user.followers.add(follower)

            no_inbox_follower = models.User.objects.create_user(
                'hamster', 'hamster@mouse.mouse', 'hamword',
                shared_inbox=None, local=False,
                remote_id='http://example.com/u/2',
                outbox='http://example.com/u/2/o',
                inbox='http://example.com/u/2/inbox')
            self.user.followers.add(no_inbox_follower)

            non_fr_follower = models.User.objects.create_user(
                'gerbil', 'gerb@mouse.mouse', 'gerbword',
                remote_id='http://example.com/u/3',
                outbox='http://example2.com/u/3/o',
                inbox='http://example2.com/u/3/inbox',
                shared_inbox='http://example2.com/inbox',
                bookwyrm_user=False, local=False)
            self.user.followers.add(non_fr_follower)

            models.User.objects.create_user(
                'nutria', 'nutria@mouse.mouse', 'nuword',
                remote_id='http://example.com/u/4',
                outbox='http://example.com/u/4/o',
                shared_inbox='http://example.com/inbox',
                inbox='http://example.com/u/4/inbox',
                local=False)


    def test_get_public_recipients(self):
        expected = [
            'http://example2.com/inbox',
            'http://example.com/inbox',
            'http://example.com/u/2/inbox',
        ]

        recipients = broadcast.get_public_recipients(self.user)
        self.assertEqual(recipients, expected)


    def test_get_public_recipients_software(self):
        expected = [
            'http://example.com/inbox',
            'http://example.com/u/2/inbox',
        ]

        recipients = broadcast.get_public_recipients(self.user, software='bookwyrm')
        self.assertEqual(recipients, expected)


    def test_get_public_recipients_software_other(self):
        expected = [
            'http://example2.com/inbox',
        ]

        recipients = broadcast.get_public_recipients(self.user, software='mastodon')
        self.assertEqual(recipients, expected)
