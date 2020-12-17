''' testing models '''
from django.test import TestCase

from bookwyrm import models, settings


class Shelf(TestCase):
    ''' some activitypub oddness ahead '''
    def setUp(self):
        ''' look, a shelf '''
        self.user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
        self.shelf = models.Shelf.objects.create(
            name='Test Shelf', identifier='test-shelf', user=self.user)

    def test_remote_id(self):
        ''' shelves use custom remote ids '''
        expected_id = 'https://%s/user/mouse/shelf/test-shelf' % settings.DOMAIN
        self.assertEqual(self.shelf.get_remote_id(), expected_id)


    def test_to_activity(self):
        ''' jsonify it '''
        activity_json = self.shelf.to_activity()
        self.assertIsInstance(activity_json, dict)
        self.assertEqual(activity_json['id'], self.shelf.remote_id)
        self.assertEqual(activity_json['totalItems'], 0)
        self.assertEqual(activity_json['type'], 'OrderedCollection')
        self.assertEqual(activity_json['name'], 'Test Shelf')
        self.assertEqual(activity_json['owner'], self.user.remote_id)
