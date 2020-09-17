''' testing models '''
from django.test import TestCase

from fedireads import models
from fedireads.settings import DOMAIN


class User(TestCase):
    def setUp(self):
        models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword')

    def test_computed_fields(self):
        ''' username instead of id here '''
        user = models.User.objects.get(localname='mouse')
        expected_id = 'https://%s/user/mouse' % DOMAIN
        self.assertEqual(user.remote_id, expected_id)
        self.assertEqual(user.username, 'mouse@%s' % DOMAIN)
        self.assertEqual(user.localname, 'mouse')
        self.assertEqual(user.shared_inbox, 'https://%s/inbox' % DOMAIN)
        self.assertEqual(user.inbox, '%s/inbox' % expected_id)
        self.assertEqual(user.outbox, '%s/outbox' % expected_id)
        self.assertIsNotNone(user.private_key)
        self.assertIsNotNone(user.public_key)


    def test_user_shelves(self):
        user = models.User.objects.get(localname='mouse')
        shelves = models.Shelf.objects.filter(user=user).all()
        self.assertEqual(len(shelves), 3)
        names = [s.name for s in shelves]
        self.assertEqual(names, ['To Read', 'Currently Reading', 'Read'])
        ids = [s.identifier for s in shelves]
        self.assertEqual(ids, ['to-read', 'reading', 'read'])
