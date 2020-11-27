from django.test import TestCase

from bookwyrm import models, incoming


class IncomingFollow(TestCase):
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


#    def test_handle_follow(self):
#        activity = {
#            "@context": "https://www.w3.org/ns/activitystreams",
#            "id": "https://example.com/users/rat/follows/123",
#            "type": "Follow",
#            "actor": "https://example.com/users/rat",
#            "object": "http://local.com/user/mouse"
#        }
#
#        incoming.handle_follow(activity)
#
#        # notification created
#        notification = models.Notification.objects.get()
#        self.assertEqual(notification.user, self.local_user)
#        self.assertEqual(notification.notification_type, 'FOLLOW')
#
#        # the request should have been deleted
#        requests = models.UserFollowRequest.objects.all()
#        self.assertEqual(list(requests), [])
#
#        # the follow relationship should exist
#        follow = models.UserFollows.objects.get(user_object=self.local_user)
#        self.assertEqual(follow.user_subject, self.remote_user)


    def test_handle_follow_manually_approved(self):
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "http://local.com/user/mouse"
        }

        self.local_user.manually_approves_followers = True
        self.local_user.save()

        incoming.handle_follow(activity)

        # notification created
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.notification_type, 'FOLLOW_REQUEST')

        # the request should exist
        request = models.UserFollowRequest.objects.get()
        self.assertEqual(request.user_subject, self.remote_user)
        self.assertEqual(request.user_object, self.local_user)

        # the follow relationship should not exist
        follow = models.UserFollows.objects.all()
        self.assertEqual(list(follow), [])


    def test_nonexistent_user_follow(self):
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "http://local.com/user/nonexistent-user"
        }

        incoming.handle_follow(activity)

        # do nothing
        notifications = models.Notification.objects.all()
        self.assertEqual(list(notifications), [])
        requests = models.UserFollowRequest.objects.all()
        self.assertEqual(list(requests), [])
        follows = models.UserFollows.objects.all()
        self.assertEqual(list(follows), [])
