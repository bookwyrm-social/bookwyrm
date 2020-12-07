''' tests the base functionality for activitypub dataclasses '''
from dataclasses import dataclass
from django.test import TestCase

from bookwyrm.activitypub.base_activity import ActivityObject, \
    find_existing_by_remote_id
from bookwyrm.activitypub import ActivitySerializerError
from bookwyrm import models

class BaseActivity(TestCase):
    ''' the super class for model-linked activitypub dataclasses '''
    def test_init(self):
        ''' simple successfuly init '''
        instance = ActivityObject(id='a', type='b')
        self.assertTrue(hasattr(instance, 'id'))
        self.assertTrue(hasattr(instance, 'type'))

    def test_init_missing(self):
        ''' init with missing required params '''
        with self.assertRaises(ActivitySerializerError):
            ActivityObject()

    def test_init_extra_fields(self):
        ''' init ignoring additional fields '''
        instance = ActivityObject(id='a', type='b', fish='c')
        self.assertTrue(hasattr(instance, 'id'))
        self.assertTrue(hasattr(instance, 'type'))

    def test_init_default_field(self):
        ''' replace an existing required field with a default field '''
        @dataclass(init=False)
        class TestClass(ActivityObject):
            ''' test class with default field '''
            type: str = 'TestObject'

        instance = TestClass(id='a')
        self.assertEqual(instance.id, 'a')
        self.assertEqual(instance.type, 'TestObject')

    def test_serialize(self):
        ''' simple function for converting dataclass to dict '''
        instance = ActivityObject(id='a', type='b')
        serialized = instance.serialize()
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized['id'], 'a')
        self.assertEqual(serialized['type'], 'b')

    def test_find_existing_by_remote_id(self):
        ''' attempt to match a remote id to an object in the db '''
        user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
        user.remote_id = 'http://example.com/a/b'
        user.save()

        # uses a different remote id scheme
        book = models.Edition.objects.create(
            title='Test Edition', remote_id='http://book.com/book')
        # this isn't really part of this test directly but it's helpful to state
        self.assertEqual(book.origin_id, 'http://book.com/book')
        self.assertNotEqual(book.remote_id, 'http://book.com/book')

        # uses subclasses
        models.Comment.objects.create(
            user=user, content='test status', book=book, \
            remote_id='https://comment.net')

        result = find_existing_by_remote_id(models.User, 'hi')
        self.assertIsNone(result)

        result = find_existing_by_remote_id(
            models.User, 'http://example.com/a/b')
        self.assertEqual(result, user)

        # test using origin id
        result = find_existing_by_remote_id(
            models.Edition, 'http://book.com/book')
        self.assertEqual(result, book)

        # test subclass match
        result = find_existing_by_remote_id(
            models.Status, 'https://comment.net')
