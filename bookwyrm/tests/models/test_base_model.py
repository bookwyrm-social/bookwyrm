''' testing models '''
from django.test import TestCase

from bookwyrm import models
from bookwyrm.models.base_model import FedireadsModel
from bookwyrm.settings import DOMAIN


class BaseModel(TestCase):
    def test_remote_id(self):
        instance = FedireadsModel()
        instance.id = 1
        expected = instance.get_remote_id()
        self.assertEqual(expected, 'https://%s/bookwyrmmodel/1' % DOMAIN)

    def test_remote_id_with_user(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword')
        instance = FedireadsModel()
        instance.user = user
        instance.id = 1
        expected = instance.get_remote_id()
        self.assertEqual(
            expected,
            'https://%s/user/mouse/bookwyrmmodel/1' % DOMAIN)
