import time
from collections import namedtuple
from urllib.parse import urlsplit
import pathlib

import json
import responses

from django.test import TestCase, Client
from django.utils.http import http_date

from fedireads.models import User
from fedireads.activitypub import get_follow_request
from fedireads.settings import DOMAIN
from fedireads.signatures import create_key_pair, make_signature, make_digest

def get_follow_data(follower, followee):
    return json.dumps(get_follow_request(follower, followee)).encode('utf-8')

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

    def send(self, signature, now, data):
        c = Client()
        return c.post(
            urlsplit(self.rat.inbox).path,
            data=data,
            content_type='application/json',
            **{
                'HTTP_DATE': now,
                'HTTP_SIGNATURE': signature,
                'HTTP_DIGEST': make_digest(data),
                'HTTP_CONTENT_TYPE': 'application/activity+json; charset=utf-8',
                'HTTP_HOST': DOMAIN,
            }
        )

    def send_test_request(
            self,
            sender,
            signer=None,
            send_data=None,
            digest=None,
            date=None):
        now = date or http_date()
        data = get_follow_data(sender, self.rat)
        signature = make_signature(
            signer or sender, self.rat.inbox, now, digest or make_digest(data))
        return self.send(signature, now, send_data or data)

    def test_correct_signature(self):
        response = self.send_test_request(sender=self.mouse)
        self.assertEqual(response.status_code, 200)

    def test_wrong_signature(self):
        ''' Messages must be signed by the right actor.
            (cat cannot sign messages on behalf of mouse)
        '''
        response = self.send_test_request(sender=self.mouse, signer=self.cat)
        self.assertEqual(response.status_code, 401)

    @responses.activate
    def test_remote_signer(self):
        datafile = pathlib.Path(__file__).parent.joinpath('data/ap_user.json')
        data = json.loads(datafile.read_bytes())
        data['id'] = self.fake_remote.remote_id
        data['publicKey']['publicKeyPem'] = self.fake_remote.public_key
        del data['icon'] # Avoid having to return an avatar.
        responses.add(
            responses.GET,
            self.fake_remote.remote_id,
            json=data,
            status=200)
        responses.add(
            responses.GET,
            'https://localhost/.well-known/nodeinfo',
            status=404)
        responses.add(
            responses.GET,
            'https://example.com/user/mouse/outbox?page=true',
            json={'orderedItems': []},
            status=200
        )

        response = self.send_test_request(sender=self.fake_remote)
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_nonexistent_signer(self):
        responses.add(
            responses.GET,
            self.fake_remote.remote_id,
            json={'error': 'not found'},
            status=404)

        response = self.send_test_request(sender=self.fake_remote)
        self.assertEqual(response.status_code, 401)

    def test_changed_data(self):
        '''Message data must match the digest header.'''
        response = self.send_test_request(
            self.mouse,
            send_data=get_follow_data(self.mouse, self.cat))
        self.assertEqual(response.status_code, 401)

    def test_invalid_digest(self):
        response = self.send_test_request(
            self.mouse,
            digest='SHA-256=AAAAAAAAAAAAAAAAAA')
        self.assertEqual(response.status_code, 401)

    def test_old_message(self):
        '''Old messages should be rejected to prevent replay attacks.'''
        response = self.send_test_request(
            self.mouse,
            date=http_date(time.time() - 301)
        )
        self.assertEqual(response.status_code, 401)
