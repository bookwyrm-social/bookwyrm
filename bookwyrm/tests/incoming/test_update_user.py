''' when a remote user changes their profile '''
import json
import pathlib
from django.test import TestCase

from bookwyrm import models, incoming


class UpdateUser(TestCase):
    def setUp(self):
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
