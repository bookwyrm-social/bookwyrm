''' testing models '''
from django.test import TestCase

from fedireads.models.base_model import FedireadsModel
from fedireads.settings import DOMAIN


class BaseModel(TestCase):
    def test_absolute_id(self):
        instance = FedireadsModel()
        instance.id = 1
        expected = instance.absolute_id
        self.assertEqual(expected, 'https://%s/fedireadsmodel/1' % DOMAIN)

    def test_absolute_id_with_remote(self):
        instance = FedireadsModel()
        instance.remote_id = 'boop doop'
        expected = instance.absolute_id
        self.assertEqual(expected, 'boop doop')
