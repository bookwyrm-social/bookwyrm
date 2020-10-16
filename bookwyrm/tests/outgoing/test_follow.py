from django.test import TestCase

from bookwyrm import models, outgoing


class OutgoingFollow(TestCase):
    def setUp(self):
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

        outgoing.handle_follow(self.local_user, self.remote_user)
        rel = models.UserFollowRequest.objects.get()

        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)
        self.assertEqual(rel.status, 'follow_request')

    def test_handle_unfollow(self):
        self.remote_user.followers.add(self.local_user)
        self.assertEqual(self.remote_user.followers.count(), 1)
        outgoing.handle_unfollow(self.local_user, self.remote_user)

        self.assertEqual(self.remote_user.followers.count(), 0)
