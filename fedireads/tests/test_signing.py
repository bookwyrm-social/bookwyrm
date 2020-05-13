from urllib.parse import urlsplit

from django.test import TestCase, Client
from django.utils.http import http_date

from fedireads.models import User
from fedireads.broadcast import make_signature
from fedireads.activitypub import get_follow_request
from fedireads.settings import DOMAIN

class Signature(TestCase):
    def setUp(self):
        self.mouse = User.objects.create_user('mouse', 'mouse@example.com', '')
        self.rat = User.objects.create_user('rat', 'rat@example.com', '')
        self.cat = User.objects.create_user('cat', 'cat@example.com', '')

    def send_follow(self, signature, now):
        c = Client()
        return c.post(
            urlsplit(self.rat.inbox).path,
            data=get_follow_request(
                self.mouse,
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
        return self.send_follow(signature, now).status_code == 200

    def test_wrong_signature(self):
        ''' Messages must be signed by the right actor.
            (cat cannot sign messages on behalf of mouse)
        '''
        now = http_date()
        signature = make_signature(self.cat, self.rat.inbox, now)
        assert self.send_follow(signature, now).status_code == 401
