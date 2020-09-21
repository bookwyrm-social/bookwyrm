import json
import pathlib
from django.test import TestCase

from bookwyrm import models, remote_user


class RemoteUser(TestCase):
    ''' not too much going on in the books model but here we are '''
    def setUp(self):
        self.remote_user = models.User.objects.create_user(
            'rat', 'rat@rat.com', 'ratword',
            local=False,
            remote_id='https://example.com/users/rat',
            inbox='https://example.com/users/rat/inbox',
            outbox='https://example.com/users/rat/outbox',
        )
        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/ap_user.json'
        )
        self.user_data = json.loads(datafile.read_bytes())



    def test_get_remote_user(self):
        actor = 'https://example.com/users/rat'
        user = remote_user.get_or_create_remote_user(actor)
        self.assertEqual(user, self.remote_user)


    def test_create_remote_user(self):
        user = remote_user.create_remote_user(self.user_data)
        self.assertFalse(user.local)
        self.assertEqual(user.remote_id, 'https://example.com/user/mouse')
        self.assertEqual(user.username, 'mouse@example.com')
        self.assertEqual(user.name, 'MOUSE?? MOUSE!!')
        self.assertEqual(user.inbox, 'https://example.com/user/mouse/inbox')
        self.assertEqual(user.outbox, 'https://example.com/user/mouse/outbox')
        self.assertEqual(user.shared_inbox, 'https://example.com/inbox')
        self.assertEqual(
            user.public_key,
            self.user_data['publicKey']['publicKeyPem']
        )
        self.assertEqual(user.local, False)
        self.assertEqual(user.bookwyrm_user, True)
        self.assertEqual(user.manually_approves_followers, False)


    def test_create_remote_user_missing_inbox(self):
        del self.user_data['inbox']
        self.assertRaises(
            TypeError,
            remote_user.create_remote_user,
            self.user_data
        )


    def test_create_remote_user_missing_outbox(self):
        del self.user_data['outbox']
        self.assertRaises(
            TypeError,
            remote_user.create_remote_user,
            self.user_data
        )


    def test_create_remote_user_default_fields(self):
        del self.user_data['manuallyApprovesFollowers']
        user = remote_user.create_remote_user(self.user_data)
        self.assertEqual(user.manually_approves_followers, False)
