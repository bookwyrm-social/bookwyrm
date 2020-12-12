# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring
import json
import pathlib
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import activitypub, models


class Person(TestCase):
    def setUp(self):
        datafile = pathlib.Path(__file__).parent.joinpath(
            '../data/ap_user.json'
        )
        self.user_data = json.loads(datafile.read_bytes())


    def test_load_user_data(self):
        activity = activitypub.Person(**self.user_data)
        self.assertEqual(activity.id, 'https://example.com/user/mouse')
        self.assertEqual(activity.preferredUsername, 'mouse')
        self.assertEqual(activity.type, 'Person')


    def test_user_to_model(self):
        activity = activitypub.Person(**self.user_data)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            user = activity.to_model(models.User)
        self.assertEqual(user.username, 'mouse@example.com')
        self.assertEqual(user.remote_id, 'https://example.com/user/mouse')
        self.assertFalse(user.local)
