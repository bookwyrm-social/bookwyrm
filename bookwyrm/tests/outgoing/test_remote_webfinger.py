''' testing user lookup '''
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase
import responses

from bookwyrm import models, outgoing
from bookwyrm.settings import DOMAIN

class TestOutgoingRemoteWebfinger(TestCase):
    ''' overwrites standard model feilds to work with activitypub '''
    def setUp(self):
        ''' get user data ready '''
        datafile = pathlib.Path(__file__).parent.joinpath(
            '../data/ap_user.json'
        )
        self.userdata = json.loads(datafile.read_bytes())
        del self.userdata['icon']

    def test_existing_user(self):
        ''' simple database lookup by username '''
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)

        result = outgoing.handle_remote_webfinger('@mouse@%s' % DOMAIN)
        self.assertEqual(result, user)

        result = outgoing.handle_remote_webfinger('mouse@%s' % DOMAIN)
        self.assertEqual(result, user)


    @responses.activate
    def test_load_user(self):
        username = 'mouse@example.com'
        wellknown = {
            "subject": "acct:mouse@example.com",
            "links": [
                {
                    "rel": "self",
                    "type": "application/activity+json",
                    "href": "https://example.com/user/mouse"
                }
            ]
        }
        responses.add(
            responses.GET,
            'https://example.com/.well-known/webfinger?resource=acct:%s' \
                    % username,
            json=wellknown,
            status=200)
        responses.add(
            responses.GET,
            'https://example.com/user/mouse',
            json=self.userdata,
            status=200)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            result = outgoing.handle_remote_webfinger('@mouse@example.com')
            self.assertIsInstance(result, models.User)
            self.assertEqual(result.username, 'mouse@example.com')
