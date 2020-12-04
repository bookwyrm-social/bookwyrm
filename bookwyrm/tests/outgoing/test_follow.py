from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models, outgoing
from bookwyrm.settings import DOMAIN


class Following(TestCase):
    def setUp(self):
        with patch('bookwyrm.models.user.set_remote_server'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )
        self.local_user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword',
            local=True,
            remote_id='http://local.com/users/mouse',
        )


    def test_handle_follow(self):
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_follow(self.local_user, self.remote_user)

        rel = models.UserFollowRequest.objects.get()

        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)
        self.assertEqual(rel.status, 'follow_request')


    def test_handle_unfollow(self):
        self.remote_user.followers.add(self.local_user)
        self.assertEqual(self.remote_user.followers.count(), 1)
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_unfollow(self.local_user, self.remote_user)

        self.assertEqual(self.remote_user.followers.count(), 0)


    def test_handle_accept(self):
        rel = models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        rel_id = rel.id

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_accept(rel)
        # request should be deleted
        self.assertEqual(
            models.UserFollowRequest.objects.filter(id=rel_id).count(), 0
        )
        # follow relationship should exist
        self.assertEqual(self.remote_user.followers.first(), self.local_user)


    def test_handle_reject(self):
        rel = models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        rel_id = rel.id

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            outgoing.handle_reject(rel)
        # request should be deleted
        self.assertEqual(
            models.UserFollowRequest.objects.filter(id=rel_id).count(), 0
        )
        # follow relationship should not exist
        self.assertEqual(
            models.UserFollows.objects.filter(id=rel_id).count(), 0
        )
