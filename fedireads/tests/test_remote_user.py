from django.test import TestCase
import json
import pathlib

from fedireads import models, remote_user


class RemoteUser(TestCase):
    ''' not too much going on in the books model but here we are '''
    def setUp(self):
        self.remote_user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword',
            local=False,
            remote_id='https://example.com/users/mouse',
            inbox='https://example.com/users/mouse/inbox',
            outbox='https://example.com/users/mouse/outbox',
        )

    def test_get_remote_user(self):
        actor = 'https://example.com/users/mouse'
        user = remote_user.get_or_create_remote_user(actor)
        self.assertEqual(user, self.remote_user)


    def test_create_remote_user(self):
        datafile = pathlib.Path(__file__).parent.joinpath('data/ap_user.json')
        data = json.loads(datafile.read_bytes())
        user = remote_user.create_remote_user(data)
        self.assertEqual(user.username, 'mouse@example.com')
        self.assertEqual(user.name, 'MOUSE?? MOUSE!!')
        self.assertEqual(user.inbox, 'https://example.com/user/mouse/inbox')
        self.assertEqual(user.outbox, 'https://example.com/user/mouse/outbox')
        self.assertEqual(user.shared_inbox, 'https://example.com/inbox')
        self.assertEqual(user.public_key, data['publicKey']['publicKeyPem'])
        self.assertEqual(user.local, False)
        self.assertEqual(user.fedireads_user, True)
        self.assertEqual(user.manually_approves_followers, False)
