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
