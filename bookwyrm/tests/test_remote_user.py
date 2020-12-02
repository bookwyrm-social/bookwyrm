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
