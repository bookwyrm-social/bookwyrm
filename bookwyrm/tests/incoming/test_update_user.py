''' when a remote user changes their profile '''
import json
import pathlib
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, incoming


class UpdateUser(TestCase):
    def setUp(self):
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            with patch('bookwyrm.models.user.get_remote_reviews.delay'):
                self.user = models.User.objects.create_user(
                    'mouse', 'mouse@mouse.com', 'mouseword',
                    remote_id='https://example.com/user/mouse',
                    local=False,
                    localname='mouse'
                )

        datafile = pathlib.Path(__file__).parent.joinpath(
            '../data/ap_user.json'
        )
        self.user_data = json.loads(datafile.read_bytes())

    def test_handle_update_user(self):
        self.assertIsNone(self.user.name)
        self.assertEqual(self.user.localname, 'mouse')

        incoming.handle_update_user({'object': self.user_data})
        self.user = models.User.objects.get(id=self.user.id)

        self.assertEqual(self.user.name, 'MOUSE?? MOUSE!!')
        self.assertEqual(self.user.localname, 'mouse')
