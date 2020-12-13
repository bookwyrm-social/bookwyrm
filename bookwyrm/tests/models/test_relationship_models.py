''' testing models '''
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


class Relationship(TestCase):
    def setUp(self):
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )
        self.local_user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword', local=True)
        self.local_user.remote_id = 'http://local.com/user/mouse'
        self.local_user.save()

    def test_user_follows(self):
        rel = models.UserFollows.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )

        self.assertEqual(
            rel.remote_id,
            'http://local.com/user/mouse#follows/%d' % rel.id
        )

        activity = rel.to_activity()
        self.assertEqual(activity['id'], rel.remote_id)
        self.assertEqual(activity['actor'], self.local_user.remote_id)
        self.assertEqual(activity['object'], self.remote_user.remote_id)

    def test_user_follow_accept_serialization(self):
        rel = models.UserFollows.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )

        self.assertEqual(
            rel.remote_id,
            'http://local.com/user/mouse#follows/%d' % rel.id
        )
        accept = rel.to_accept_activity()
        self.assertEqual(accept['type'], 'Accept')
        self.assertEqual(
            accept['id'],
            'http://local.com/user/mouse#accepts/%d' % rel.id
        )
        self.assertEqual(accept['actor'], self.remote_user.remote_id)
        self.assertEqual(accept['object']['id'], rel.remote_id)
        self.assertEqual(accept['object']['actor'], self.local_user.remote_id)
        self.assertEqual(accept['object']['object'], self.remote_user.remote_id)

    def test_user_follow_reject_serialization(self):
        rel = models.UserFollows.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )

        self.assertEqual(
            rel.remote_id,
            'http://local.com/user/mouse#follows/%d' % rel.id
        )
        reject = rel.to_reject_activity()
        self.assertEqual(reject['type'], 'Reject')
        self.assertEqual(
            reject['id'],
            'http://local.com/user/mouse#rejects/%d' % rel.id
        )
        self.assertEqual(reject['actor'], self.remote_user.remote_id)
        self.assertEqual(reject['object']['id'], rel.remote_id)
        self.assertEqual(reject['object']['actor'], self.local_user.remote_id)
        self.assertEqual(reject['object']['object'], self.remote_user.remote_id)


    def test_user_follows_from_request(self):
        request = models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        self.assertEqual(
            request.remote_id,
            'http://local.com/user/mouse#follows/%d' % request.id
        )
        self.assertEqual(request.status, 'follow_request')

        rel = models.UserFollows.from_request(request)
        self.assertEqual(
            rel.remote_id,
            'http://local.com/user/mouse#follows/%d' % request.id
        )
        self.assertEqual(rel.status, 'follows')
        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)


    def test_user_follows_from_request_custom_remote_id(self):
        request = models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
            remote_id='http://antoher.server/sdkfhskdjf/23'
        )
        self.assertEqual(
            request.remote_id,
            'http://antoher.server/sdkfhskdjf/23'
        )
        self.assertEqual(request.status, 'follow_request')

        rel = models.UserFollows.from_request(request)
        self.assertEqual(
            rel.remote_id,
            'http://antoher.server/sdkfhskdjf/23'
        )
        self.assertEqual(rel.status, 'follows')
        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)
