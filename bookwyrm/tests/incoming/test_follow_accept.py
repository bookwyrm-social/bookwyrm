from django.test import TestCase

from bookwyrm import models, incoming


class IncomingFollowAccept(TestCase):
    def setUp(self):
        self.remote_user = models.User.objects.create_user(
            'rat', 'rat@rat.com', 'ratword',
            local=False,
            remote_id='https://example.com/users/rat',
            inbox='https://example.com/users/rat/inbox',
            outbox='https://example.com/users/rat/outbox',
        )
        self.local_user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword')
        self.local_user.remote_id = 'http://local.com/user/mouse'
        self.local_user.save()


    def test_handle_follow_accept(self):
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123#accepts",
            "type": "Accept",
            "actor": "https://example.com/users/rat",
            "object": {
                "id": "https://example.com/users/rat/follows/123",
                "type": "Follow",
                "actor": "http://local.com/user/mouse",
                "object": "https://example.com/users/rat"
            }
        }

        models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        self.assertEqual(models.UserFollowRequest.objects.count(), 1)

        incoming.handle_follow_accept(activity)

        # request should be deleted
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        # relationship should be created
        follows = self.remote_user.followers
        self.assertEqual(follows.count(), 1)
        self.assertEqual(follows.first(), self.local_user)
