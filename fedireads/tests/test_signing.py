from collections import namedtuple
from urllib.parse import urlsplit

import responses

from django.test import TestCase, Client
from django.utils.http import http_date

from fedireads.models import User
from fedireads.activitypub import get_follow_request
from fedireads.settings import DOMAIN
from fedireads.signatures import create_key_pair, make_signature

Sender = namedtuple('Sender', ('remote_id', 'private_key', 'public_key'))

class Signature(TestCase):
    def setUp(self):
        self.mouse = User.objects.create_user('mouse', 'mouse@example.com', '')
        self.rat = User.objects.create_user('rat', 'rat@example.com', '')
        self.cat = User.objects.create_user('cat', 'cat@example.com', '')

        private_key, public_key = create_key_pair()

        self.fake_remote = Sender(
            'http://localhost/user/remote',
            private_key,
            public_key,
        )

    def send_follow(self, sender, signature, now):
        c = Client()
        return c.post(
            urlsplit(self.rat.inbox).path,
            data=get_follow_request(
                sender,
                self.rat,
            ),
            content_type='application/json',
            **{
                'HTTP_DATE': now,
                'HTTP_SIGNATURE': signature,
                'HTTP_CONTENT_TYPE': 'application/activity+json; charset=utf-8',
                'HTTP_HOST': DOMAIN,
            }
        )

    def test_correct_signature(self):
        now = http_date()
        signature = make_signature(self.mouse, self.rat.inbox, now)
        return self.send_follow(self.mouse, signature, now).status_code == 200

    def test_wrong_signature(self):
        ''' Messages must be signed by the right actor.
            (cat cannot sign messages on behalf of mouse)
        '''
        now = http_date()
        signature = make_signature(self.cat, self.rat.inbox, now)
        assert self.send_follow(self.mouse, signature, now).status_code == 401

    @responses.activate
    def test_remote_signer(self):
        responses.add(
            responses.GET,
            self.fake_remote.remote_id,
            json={'publicKey': {
                'publicKeyPem': self.fake_remote.public_key
            }},
            status=200)

        now = http_date()
        sender = self.fake_remote
        signature = make_signature(sender, self.rat.inbox, now)
        response = self.send_follow(sender, signature, now)
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_nonexistent_signer(self):
        responses.add(
            responses.GET,
            self.fake_remote.remote_id,
            json={'error': 'not found'},
            status=404)

        now = http_date()
        sender = self.fake_remote
        signature = make_signature(sender, self.rat.inbox, now)
        response = self.send_follow(sender, signature, now)
        self.assertEqual(response.status_code, 401)
