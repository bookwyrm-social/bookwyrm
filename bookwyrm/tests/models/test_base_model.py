''' testing models '''
from collections import namedtuple
from django.test import TestCase

from bookwyrm import models
from bookwyrm.models import base_model
from bookwyrm.models.base_model import ActivitypubMixin
from bookwyrm.settings import DOMAIN

class BaseModel(TestCase):
    def test_remote_id(self):
        instance = base_model.BookWyrmModel()
        instance.id = 1
        expected = instance.get_remote_id()
        self.assertEqual(expected, 'https://%s/bookwyrmmodel/1' % DOMAIN)

    def test_remote_id_with_user(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword', local=True)
        instance = base_model.BookWyrmModel()
        instance.user = user
        instance.id = 1
        expected = instance.get_remote_id()
        self.assertEqual(
            expected,
            'https://%s/user/mouse/bookwyrmmodel/1' % DOMAIN)

    def test_execute_after_save(self):
        ''' this function sets remote ids after creation '''
        # using Work because it BookWrymModel is abstract and this requires save
        # Work is a relatively not-fancy model.
        instance = models.Work.objects.create(title='work title')
        instance.remote_id = None
        base_model.execute_after_save(None, instance, True)
        self.assertEqual(
            instance.remote_id,
            'https://%s/book/%d' % (DOMAIN, instance.id)
        )

        # shouldn't set remote_id if it's not created
        instance.remote_id = None
        base_model.execute_after_save(None, instance, False)
        self.assertIsNone(instance.remote_id)

    def test_to_create_activity(self):
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword', local=True)

        object_activity = {
            'to': 'to field', 'cc': 'cc field',
            'content': 'hi',
            'published': '2020-12-04T17:52:22.623807+00:00',
        }
        MockSelf = namedtuple('Self', ('remote_id', 'to_activity'))
        mock_self = MockSelf(
            'https://example.com/status/1',
            lambda *args: object_activity
        )
        activity = ActivitypubMixin.to_create_activity(mock_self, user)
        self.assertEqual(
            activity['id'],
            'https://example.com/status/1/activity'
        )
        self.assertEqual(activity['actor'], user.remote_id)
        self.assertEqual(activity['to'], 'to field')
        self.assertEqual(activity['cc'], 'cc field')
        self.assertEqual(activity['object'], object_activity)
        self.assertEqual(
            activity['signature'].creator,
            '%s#main-key' % user.remote_id
        )
