''' testing models '''
from collections import namedtuple
from dataclasses import dataclass
import re
from django.test import TestCase

from bookwyrm.activitypub.base_activity import ActivityObject
from bookwyrm import models
from bookwyrm.models import base_model
from bookwyrm.models.base_model import ActivitypubMixin
from bookwyrm.settings import DOMAIN

class BaseModel(TestCase):
    ''' functionality shared across models '''
    def test_remote_id(self):
        ''' these should be generated '''
        instance = base_model.BookWyrmModel()
        instance.id = 1
        expected = instance.get_remote_id()
        self.assertEqual(expected, 'https://%s/bookwyrmmodel/1' % DOMAIN)

    def test_remote_id_with_user(self):
        ''' format of remote id when there's a user object '''
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
        ''' wrapper for ActivityPub "create" action '''
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
        self.assertEqual(activity['type'], 'Create')
        self.assertEqual(activity['to'], 'to field')
        self.assertEqual(activity['cc'], 'cc field')
        self.assertEqual(activity['object'], object_activity)
        self.assertEqual(
            activity['signature'].creator,
            '%s#main-key' % user.remote_id
        )

    def test_to_delete_activity(self):
        ''' wrapper for Delete activity '''
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword', local=True)

        MockSelf = namedtuple('Self', ('remote_id', 'to_activity'))
        mock_self = MockSelf(
            'https://example.com/status/1',
            lambda *args: {}
        )
        activity = ActivitypubMixin.to_delete_activity(mock_self, user)
        self.assertEqual(
            activity['id'],
            'https://example.com/status/1/activity'
        )
        self.assertEqual(activity['actor'], user.remote_id)
        self.assertEqual(activity['type'], 'Delete')
        self.assertEqual(
            activity['to'],
            ['%s/followers' % user.remote_id])
        self.assertEqual(
            activity['cc'],
            ['https://www.w3.org/ns/activitystreams#Public'])

    def test_to_update_activity(self):
        ''' ditto above but for Update '''
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword', local=True)

        MockSelf = namedtuple('Self', ('remote_id', 'to_activity'))
        mock_self = MockSelf(
            'https://example.com/status/1',
            lambda *args: {}
        )
        activity = ActivitypubMixin.to_update_activity(mock_self, user)
        self.assertIsNotNone(
            re.match(
                r'^https:\/\/example\.com\/status\/1#update\/.*',
                activity['id']
            )
        )
        self.assertEqual(activity['actor'], user.remote_id)
        self.assertEqual(activity['type'], 'Update')
        self.assertEqual(
            activity['to'],
            ['https://www.w3.org/ns/activitystreams#Public'])
        self.assertEqual(activity['object'], {})

    def test_to_undo_activity(self):
        ''' and again, for Undo '''
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword', local=True)

        MockSelf = namedtuple('Self', ('remote_id', 'to_activity'))
        mock_self = MockSelf(
            'https://example.com/status/1',
            lambda *args: {}
        )
        activity = ActivitypubMixin.to_undo_activity(mock_self, user)
        self.assertEqual(
            activity['id'],
            'https://example.com/status/1#undo'
        )
        self.assertEqual(activity['actor'], user.remote_id)
        self.assertEqual(activity['type'], 'Undo')
        self.assertEqual(activity['object'], {})


    def test_to_activity(self):
        ''' model to ActivityPub json '''
        @dataclass(init=False)
        class TestActivity(ActivityObject):
            ''' real simple mock '''
            type: str = 'Test'

        class TestModel(ActivitypubMixin, base_model.BookWyrmModel):
            ''' real simple mock model because BookWyrmModel is abstract '''

        instance = TestModel()
        instance.remote_id = 'https://www.example.com/test'
        instance.activity_serializer = TestActivity

        activity = instance.to_activity()
        self.assertIsInstance(activity, dict)
        self.assertEqual(activity['id'], 'https://www.example.com/test')
        self.assertEqual(activity['type'], 'Test')


    def test_find_existing_by_remote_id(self):
        ''' attempt to match a remote id to an object in the db '''
        # uses a different remote id scheme
        # this isn't really part of this test directly but it's helpful to state
        book = models.Edition.objects.create(
            title='Test Edition', remote_id='http://book.com/book')
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
        user.remote_id = 'http://example.com/a/b'
        user.save()

        self.assertEqual(book.origin_id, 'http://book.com/book')
        self.assertNotEqual(book.remote_id, 'http://book.com/book')

        # uses subclasses
        models.Comment.objects.create(
            user=user, content='test status', book=book, \
            remote_id='https://comment.net')

        result = models.User.find_existing_by_remote_id('hi')
        self.assertIsNone(result)

        result = models.User.find_existing_by_remote_id(
            'http://example.com/a/b')
        self.assertEqual(result, user)

        # test using origin id
        result = models.Edition.find_existing_by_remote_id(
            'http://book.com/book')
        self.assertEqual(result, book)

        # test subclass match
        result = models.Status.find_existing_by_remote_id(
            'https://comment.net')
