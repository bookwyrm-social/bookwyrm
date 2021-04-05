""" tests incoming activities"""
from datetime import datetime
import json
import pathlib
from unittest.mock import patch

from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.test import TestCase, Client
import responses

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class Inbox(TestCase):
    """ readthrough tests """

    def setUp(self):
        """ basic user and book data """
        self.client = Client()
        self.local_user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
        )
        self.local_user.remote_id = "https://example.com/user/mouse"
        self.local_user.save(broadcast=False)
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
                self.status = models.Status.objects.create(
                    user=self.local_user,
                    content="Test status",
                    remote_id="https://example.com/status/1",
                )

        self.create_json = {
            "id": "hi",
            "type": "Create",
            "actor": "hi",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {},
        }
        models.SiteSettings.objects.create()

    def test_inbox_invalid_get(self):
        """ shouldn't try to handle if the user is not found """
        result = self.client.get("/inbox", content_type="application/json")
        self.assertIsInstance(result, HttpResponseNotAllowed)

    def test_inbox_invalid_user(self):
        """ shouldn't try to handle if the user is not found """
        result = self.client.post(
            "/user/bleh/inbox",
            '{"type": "Test", "object": "exists"}',
            content_type="application/json",
        )
        self.assertIsInstance(result, HttpResponseNotFound)

    def test_inbox_invalid_bad_signature(self):
        """ bad request for invalid signature """
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            mock_valid.return_value = False
            result = self.client.post(
                "/user/mouse/inbox",
                '{"type": "Announce", "object": "exists"}',
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 401)

    def test_inbox_invalid_bad_signature_delete(self):
        """ invalid signature for Delete is okay though """
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            mock_valid.return_value = False
            result = self.client.post(
                "/user/mouse/inbox",
                '{"type": "Delete", "object": "exists"}',
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 200)

    def test_inbox_unknown_type(self):
        """ never heard of that activity type, don't have a handler for it """
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            result = self.client.post(
                "/inbox",
                '{"type": "Fish", "object": "exists"}',
                content_type="application/json",
            )
            mock_valid.return_value = True
            self.assertIsInstance(result, HttpResponseNotFound)

    def test_inbox_success(self):
        """ a known type, for which we start a task """
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/list/22",
            "type": "BookList",
            "totalItems": 1,
            "first": "https://example.com/list/22?page=1",
            "last": "https://example.com/list/22?page=1",
            "name": "Test List",
            "owner": "https://example.com/user/mouse",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "summary": "summary text",
            "curation": "curated",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        with patch("bookwyrm.views.inbox.has_valid_signature") as mock_valid:
            mock_valid.return_value = True

            with patch("bookwyrm.views.inbox.activity_task.delay"):
                result = self.client.post(
                    "/inbox", json.dumps(activity), content_type="application/json"
                )
        self.assertEqual(result.status_code, 200)

    def test_handle_create_status(self):
        """ the "it justs works" mode """
        self.assertEqual(models.Status.objects.count(), 1)

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_quotation.json")
        status_data = json.loads(datafile.read_bytes())
        models.Edition.objects.create(
            title="Test Book", remote_id="https://example.com/book/1"
        )
        activity = self.create_json
        activity["object"] = status_data

        with patch("bookwyrm.activitystreams.ActivityStream.add_status") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)

        status = models.Quotation.objects.get()
        self.assertEqual(
            status.remote_id, "https://example.com/user/mouse/quotation/13"
        )
        self.assertEqual(status.quote, "quote body")
        self.assertEqual(status.content, "commentary")
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(models.Status.objects.count(), 2)

        # while we're here, lets ensure we avoid dupes
        views.inbox.activity_task(activity)
        self.assertEqual(models.Status.objects.count(), 2)

    def test_handle_create_status_remote_note_with_mention(self):
        """ should only create it under the right circumstances """
        self.assertEqual(models.Status.objects.count(), 1)
        self.assertFalse(
            models.Notification.objects.filter(user=self.local_user).exists()
        )

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        activity = self.create_json
        activity["object"] = status_data

        with patch("bookwyrm.activitystreams.ActivityStream.add_status") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        status = models.Status.objects.last()
        self.assertEqual(status.content, "test content in note")
        self.assertEqual(status.mention_users.first(), self.local_user)
        self.assertTrue(
            models.Notification.objects.filter(user=self.local_user).exists()
        )
        self.assertEqual(models.Notification.objects.get().notification_type, "MENTION")

    def test_handle_create_status_remote_note_with_reply(self):
        """ should only create it under the right circumstances """
        self.assertEqual(models.Status.objects.count(), 1)
        self.assertFalse(models.Notification.objects.filter(user=self.local_user))

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_note.json")
        status_data = json.loads(datafile.read_bytes())
        del status_data["tag"]
        status_data["inReplyTo"] = self.status.remote_id
        activity = self.create_json
        activity["object"] = status_data

        with patch("bookwyrm.activitystreams.ActivityStream.add_status") as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        status = models.Status.objects.last()
        self.assertEqual(status.content, "test content in note")
        self.assertEqual(status.reply_parent, self.status)
        self.assertTrue(models.Notification.objects.filter(user=self.local_user))
        self.assertEqual(models.Notification.objects.get().notification_type, "REPLY")

    def test_handle_create_list(self):
        """ a new list """
        activity = self.create_json
        activity["object"] = {
            "id": "https://example.com/list/22",
            "type": "BookList",
            "totalItems": 1,
            "first": "https://example.com/list/22?page=1",
            "last": "https://example.com/list/22?page=1",
            "name": "Test List",
            "owner": "https://example.com/user/mouse",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "summary": "summary text",
            "curation": "curated",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        book_list = models.List.objects.get()
        self.assertEqual(book_list.name, "Test List")
        self.assertEqual(book_list.curation, "curated")
        self.assertEqual(book_list.description, "summary text")
        self.assertEqual(book_list.remote_id, "https://example.com/list/22")

    def test_handle_follow(self):
        """ remote user wants to follow local user """
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse",
        }

        self.assertFalse(models.UserFollowRequest.objects.exists())
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.inbox.activity_task(activity)
            self.assertEqual(mock.call_count, 1)

        # notification created
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.notification_type, "FOLLOW")

        # the request should have been deleted
        self.assertFalse(models.UserFollowRequest.objects.exists())

        # the follow relationship should exist
        follow = models.UserFollows.objects.get(user_object=self.local_user)
        self.assertEqual(follow.user_subject, self.remote_user)

    def test_handle_follow_manually_approved(self):
        """ needs approval before following """
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse",
        }

        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.inbox.activity_task(activity)

        # notification created
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.notification_type, "FOLLOW_REQUEST")

        # the request should exist
        request = models.UserFollowRequest.objects.get()
        self.assertEqual(request.user_subject, self.remote_user)
        self.assertEqual(request.user_object, self.local_user)

        # the follow relationship should not exist
        follow = models.UserFollows.objects.all()
        self.assertEqual(list(follow), [])

    def test_handle_undo_follow_request(self):
        """ the requester cancels a follow request """
        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            request = models.UserFollowRequest.objects.create(
                user_subject=self.remote_user, user_object=self.local_user
            )
        self.assertTrue(self.local_user.follower_requests.exists())

        activity = {
            "type": "Undo",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "actor": self.remote_user.remote_id,
            "@context": "https://www.w3.org/ns/activitystreams",
            "object": {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": request.remote_id,
                "type": "Follow",
                "actor": "https://example.com/users/rat",
                "object": "https://example.com/user/mouse",
            },
        }

        views.inbox.activity_task(activity)

        self.assertFalse(self.local_user.follower_requests.exists())

    def test_handle_unfollow(self):
        """ remove a relationship """
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            rel = models.UserFollows.objects.create(
                user_subject=self.remote_user, user_object=self.local_user
            )
        activity = {
            "type": "Undo",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "actor": self.remote_user.remote_id,
            "@context": "https://www.w3.org/ns/activitystreams",
            "object": {
                "id": rel.remote_id,
                "type": "Follow",
                "actor": "https://example.com/users/rat",
                "object": "https://example.com/user/mouse",
            },
        }
        self.assertEqual(self.remote_user, self.local_user.followers.first())

        views.inbox.activity_task(activity)
        self.assertIsNone(self.local_user.followers.first())

    def test_handle_follow_accept(self):
        """ a remote user approved a follow request from local """
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            rel = models.UserFollowRequest.objects.create(
                user_subject=self.local_user, user_object=self.remote_user
            )
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123#accepts",
            "type": "Accept",
            "actor": "https://example.com/users/rat",
            "object": {
                "id": rel.remote_id,
                "type": "Follow",
                "actor": "https://example.com/user/mouse",
                "object": "https://example.com/users/rat",
            },
        }

        self.assertEqual(models.UserFollowRequest.objects.count(), 1)

        views.inbox.activity_task(activity)

        # request should be deleted
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        # relationship should be created
        follows = self.remote_user.followers
        self.assertEqual(follows.count(), 1)
        self.assertEqual(follows.first(), self.local_user)

    def test_handle_follow_reject(self):
        """ turn down a follow request """
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            rel = models.UserFollowRequest.objects.create(
                user_subject=self.local_user, user_object=self.remote_user
            )
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123#accepts",
            "type": "Reject",
            "actor": "https://example.com/users/rat",
            "object": {
                "id": rel.remote_id,
                "type": "Follow",
                "actor": "https://example.com/user/mouse",
                "object": "https://example.com/users/rat",
            },
        }

        self.assertEqual(models.UserFollowRequest.objects.count(), 1)

        views.inbox.activity_task(activity)

        # request should be deleted
        self.assertFalse(models.UserFollowRequest.objects.exists())
        self.assertFalse(self.remote_user.followers.exists())

    def test_handle_update_list(self):
        """ a new list """
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            book_list = models.List.objects.create(
                name="hi", remote_id="https://example.com/list/22", user=self.local_user
            )
        activity = {
            "type": "Update",
            "to": [],
            "cc": [],
            "actor": "hi",
            "id": "sdkjf",
            "object": {
                "id": "https://example.com/list/22",
                "type": "BookList",
                "totalItems": 1,
                "first": "https://example.com/list/22?page=1",
                "last": "https://example.com/list/22?page=1",
                "name": "Test List",
                "owner": "https://example.com/user/mouse",
                "to": ["https://www.w3.org/ns/activitystreams#Public"],
                "cc": ["https://example.com/user/mouse/followers"],
                "summary": "summary text",
                "curation": "curated",
                "@context": "https://www.w3.org/ns/activitystreams",
            },
        }
        views.inbox.activity_task(activity)
        book_list.refresh_from_db()
        self.assertEqual(book_list.name, "Test List")
        self.assertEqual(book_list.curation, "curated")
        self.assertEqual(book_list.description, "summary text")
        self.assertEqual(book_list.remote_id, "https://example.com/list/22")

    def test_handle_delete_status(self):
        """ remove a status """
        self.status.user = self.remote_user
        self.status.save(broadcast=False)

        self.assertFalse(self.status.deleted)
        activity = {
            "type": "Delete",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "id": "%s/activity" % self.status.remote_id,
            "actor": self.remote_user.remote_id,
            "object": {"id": self.status.remote_id, "type": "Tombstone"},
        }
        with patch(
            "bookwyrm.activitystreams.ActivityStream.remove_status"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        # deletion doens't remove the status, it turns it into a tombstone
        status = models.Status.objects.get()
        self.assertTrue(status.deleted)
        self.assertIsInstance(status.deleted_date, datetime)

    def test_handle_delete_status_notifications(self):
        """ remove a status with related notifications """
        self.status.user = self.remote_user
        self.status.save(broadcast=False)
        models.Notification.objects.create(
            related_status=self.status,
            user=self.local_user,
            notification_type="MENTION",
        )
        # this one is innocent, don't delete it
        notif = models.Notification.objects.create(
            user=self.local_user, notification_type="MENTION"
        )
        self.assertFalse(self.status.deleted)
        self.assertEqual(models.Notification.objects.count(), 2)
        activity = {
            "type": "Delete",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "id": "%s/activity" % self.status.remote_id,
            "actor": self.remote_user.remote_id,
            "object": {"id": self.status.remote_id, "type": "Tombstone"},
        }
        with patch(
            "bookwyrm.activitystreams.ActivityStream.remove_status"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        # deletion doens't remove the status, it turns it into a tombstone
        status = models.Status.objects.get()
        self.assertTrue(status.deleted)
        self.assertIsInstance(status.deleted_date, datetime)

        # notifications should be truly deleted
        self.assertEqual(models.Notification.objects.count(), 1)
        self.assertEqual(models.Notification.objects.get(), notif)

    def test_handle_favorite(self):
        """ fav a status """
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/fav/1",
            "actor": "https://example.com/users/rat",
            "type": "Like",
            "published": "Mon, 25 May 2020 19:31:20 GMT",
            "object": self.status.remote_id,
        }

        views.inbox.activity_task(activity)

        fav = models.Favorite.objects.get(remote_id="https://example.com/fav/1")
        self.assertEqual(fav.status, self.status)
        self.assertEqual(fav.remote_id, "https://example.com/fav/1")
        self.assertEqual(fav.user, self.remote_user)

    def test_ignore_favorite(self):
        """ don't try to save an unknown status """
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/fav/1",
            "actor": "https://example.com/users/rat",
            "type": "Like",
            "published": "Mon, 25 May 2020 19:31:20 GMT",
            "object": "https://unknown.status/not-found",
        }

        views.inbox.activity_task(activity)

        self.assertFalse(models.Favorite.objects.exists())

    def test_handle_unfavorite(self):
        """ fav a status """
        activity = {
            "id": "https://example.com/fav/1#undo",
            "type": "Undo",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "actor": self.remote_user.remote_id,
            "object": {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": "https://example.com/fav/1",
                "actor": "https://example.com/users/rat",
                "type": "Like",
                "published": "Mon, 25 May 2020 19:31:20 GMT",
                "object": self.status.remote_id,
            },
        }
        models.Favorite.objects.create(
            status=self.status,
            user=self.remote_user,
            remote_id="https://example.com/fav/1",
        )
        self.assertEqual(models.Favorite.objects.count(), 1)

        views.inbox.activity_task(activity)
        self.assertEqual(models.Favorite.objects.count(), 0)

    @patch("bookwyrm.activitystreams.ActivityStream.add_status")
    def test_handle_boost(self, _):
        """ boost a status """
        self.assertEqual(models.Notification.objects.count(), 0)
        activity = {
            "type": "Announce",
            "id": "%s/boost" % self.status.remote_id,
            "actor": self.remote_user.remote_id,
            "object": self.status.remote_id,
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "published": "Mon, 25 May 2020 19:31:20 GMT",
        }
        with patch("bookwyrm.models.status.Status.ignore_activity") as discarder:
            discarder.return_value = False
            views.inbox.activity_task(activity)
        boost = models.Boost.objects.get()
        self.assertEqual(boost.boosted_status, self.status)
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_status, self.status)

    @responses.activate
    def test_handle_discarded_boost(self):
        """ test a boost of a mastodon status that will be discarded """
        status = models.Status(
            content="hi",
            user=self.remote_user,
        )
        with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
            status.save(broadcast=False)
        activity = {
            "type": "Announce",
            "id": "http://www.faraway.com/boost/12",
            "actor": self.remote_user.remote_id,
            "object": status.remote_id,
        }
        responses.add(
            responses.GET, status.remote_id, json=status.to_activity(), status=200
        )
        views.inbox.activity_task(activity)
        self.assertEqual(models.Boost.objects.count(), 0)

    def test_handle_unboost(self):
        """ undo a boost """
        with patch("bookwyrm.activitystreams.ActivityStream.add_status"):
            boost = models.Boost.objects.create(
                boosted_status=self.status, user=self.remote_user
            )
        activity = {
            "type": "Undo",
            "actor": "hi",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {
                "type": "Announce",
                "id": boost.remote_id,
                "actor": self.remote_user.remote_id,
                "object": self.status.remote_id,
                "to": ["https://www.w3.org/ns/activitystreams#public"],
                "cc": ["https://example.com/user/mouse/followers"],
                "published": "Mon, 25 May 2020 19:31:20 GMT",
            },
        }
        with patch(
            "bookwyrm.activitystreams.ActivityStream.remove_status"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        self.assertFalse(models.Boost.objects.exists())

    def test_handle_unboost_unknown_boost(self):
        """ undo a boost """
        activity = {
            "type": "Undo",
            "actor": "hi",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {
                "type": "Announce",
                "id": "http://fake.com/unknown/boost",
                "actor": self.remote_user.remote_id,
                "object": self.status.remote_id,
            },
        }
        views.inbox.activity_task(activity)

    def test_handle_add_book_to_shelf(self):
        """ shelving a book """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )
        shelf = models.Shelf.objects.create(user=self.remote_user, name="Test Shelf")
        shelf.remote_id = "https://bookwyrm.social/user/mouse/shelf/to-read"
        shelf.save()

        activity = {
            "id": "https://bookwyrm.social/shelfbook/6189#add",
            "type": "Add",
            "actor": "https://example.com/users/rat",
            "object": {
                "type": "Edition",
                "title": "Test Title",
                "work": work.remote_id,
                "id": "https://bookwyrm.social/book/37292",
            },
            "target": "https://bookwyrm.social/user/mouse/shelf/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        self.assertEqual(shelf.books.first(), book)

    def test_handle_unshelve_book(self):
        """ remove a book from a shelf """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )
        shelf = models.Shelf.objects.create(user=self.remote_user, name="Test Shelf")
        shelf.remote_id = "https://bookwyrm.social/user/mouse/shelf/to-read"
        shelf.save()

        shelfbook = models.ShelfBook.objects.create(
            user=self.remote_user, shelf=shelf, book=book
        )

        self.assertEqual(shelf.books.first(), book)
        self.assertEqual(shelf.books.count(), 1)

        activity = {
            "id": shelfbook.remote_id,
            "type": "Remove",
            "actor": "https://example.com/users/rat",
            "object": {
                "type": "Edition",
                "title": "Test Title",
                "work": work.remote_id,
                "id": "https://bookwyrm.social/book/37292",
            },
            "target": "https://bookwyrm.social/user/mouse/shelf/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)
        self.assertFalse(shelf.books.exists())

    @responses.activate
    def test_handle_add_book_to_list(self):
        """ listing a book """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )

        responses.add(
            responses.GET,
            "https://bookwyrm.social/user/mouse/list/to-read",
            json={
                "id": "https://example.com/list/22",
                "type": "BookList",
                "totalItems": 1,
                "first": "https://example.com/list/22?page=1",
                "last": "https://example.com/list/22?page=1",
                "name": "Test List",
                "owner": "https://example.com/user/mouse",
                "to": ["https://www.w3.org/ns/activitystreams#Public"],
                "cc": ["https://example.com/user/mouse/followers"],
                "summary": "summary text",
                "curation": "curated",
                "@context": "https://www.w3.org/ns/activitystreams",
            },
        )

        activity = {
            "id": "https://bookwyrm.social/listbook/6189#add",
            "type": "Add",
            "actor": "https://example.com/users/rat",
            "object": {
                "type": "Edition",
                "title": "Test Title",
                "work": work.remote_id,
                "id": "https://bookwyrm.social/book/37292",
            },
            "target": "https://bookwyrm.social/user/mouse/list/to-read",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)

        booklist = models.List.objects.get()
        self.assertEqual(booklist.name, "Test List")
        self.assertEqual(booklist.books.first(), book)

    @responses.activate
    def test_handle_tag_book(self):
        """ listing a book """
        work = models.Work.objects.create(title="work title")
        book = models.Edition.objects.create(
            title="Test",
            remote_id="https://bookwyrm.social/book/37292",
            parent_work=work,
        )

        responses.add(
            responses.GET,
            "https://www.example.com/tag/cool-tag",
            json={
                "id": "https://1b1a78582461.ngrok.io/tag/tag",
                "type": "OrderedCollection",
                "totalItems": 0,
                "first": "https://1b1a78582461.ngrok.io/tag/tag?page=1",
                "last": "https://1b1a78582461.ngrok.io/tag/tag?page=1",
                "name": "cool tag",
                "@context": "https://www.w3.org/ns/activitystreams",
            },
        )

        activity = {
            "id": "https://bookwyrm.social/listbook/6189#add",
            "type": "Add",
            "actor": "https://example.com/users/rat",
            "object": {
                "type": "Edition",
                "title": "Test Title",
                "work": work.remote_id,
                "id": "https://bookwyrm.social/book/37292",
            },
            "target": "https://www.example.com/tag/cool-tag",
            "@context": "https://www.w3.org/ns/activitystreams",
        }
        views.inbox.activity_task(activity)

        tag = models.Tag.objects.get()
        self.assertFalse(models.List.objects.exists())
        self.assertEqual(tag.name, "cool tag")
        self.assertEqual(tag.books.first(), book)

    def test_handle_update_user(self):
        """ update an existing user """
        # we only do this with remote users
        self.local_user.local = False
        self.local_user.save()

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        userdata = json.loads(datafile.read_bytes())
        del userdata["icon"]
        self.assertIsNone(self.local_user.name)
        views.inbox.activity_task(
            {
                "type": "Update",
                "to": [],
                "cc": [],
                "actor": "hi",
                "id": "sdkjf",
                "object": userdata,
            }
        )
        user = models.User.objects.get(id=self.local_user.id)
        self.assertEqual(user.name, "MOUSE?? MOUSE!!")
        self.assertEqual(user.username, "mouse@example.com")
        self.assertEqual(user.localname, "mouse")
        self.assertTrue(user.discoverable)

    def test_handle_update_edition(self):
        """ update an existing edition """
        datafile = pathlib.Path(__file__).parent.joinpath("../data/bw_edition.json")
        bookdata = json.loads(datafile.read_bytes())

        models.Work.objects.create(
            title="Test Work", remote_id="https://bookwyrm.social/book/5988"
        )
        book = models.Edition.objects.create(
            title="Test Book", remote_id="https://bookwyrm.social/book/5989"
        )

        del bookdata["authors"]
        self.assertEqual(book.title, "Test Book")

        with patch("bookwyrm.activitypub.base_activity.set_related_field.delay"):
            views.inbox.activity_task(
                {
                    "type": "Update",
                    "to": [],
                    "cc": [],
                    "actor": "hi",
                    "id": "sdkjf",
                    "object": bookdata,
                }
            )
        book = models.Edition.objects.get(id=book.id)
        self.assertEqual(book.title, "Piranesi")

    def test_handle_update_work(self):
        """ update an existing edition """
        datafile = pathlib.Path(__file__).parent.joinpath("../data/bw_work.json")
        bookdata = json.loads(datafile.read_bytes())

        book = models.Work.objects.create(
            title="Test Book", remote_id="https://bookwyrm.social/book/5988"
        )

        del bookdata["authors"]
        self.assertEqual(book.title, "Test Book")
        with patch("bookwyrm.activitypub.base_activity.set_related_field.delay"):
            views.inbox.activity_task(
                {
                    "type": "Update",
                    "to": [],
                    "cc": [],
                    "actor": "hi",
                    "id": "sdkjf",
                    "object": bookdata,
                }
            )
        book = models.Work.objects.get(id=book.id)
        self.assertEqual(book.title, "Piranesi")

    def test_handle_blocks(self):
        """ create a "block" database entry from an activity """
        self.local_user.followers.add(self.remote_user)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.UserFollowRequest.objects.create(
                user_subject=self.local_user, user_object=self.remote_user
            )
        self.assertTrue(models.UserFollows.objects.exists())
        self.assertTrue(models.UserFollowRequest.objects.exists())

        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/9e1f41ac-9ddd-4159",
            "type": "Block",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse",
        }

        with patch(
            "bookwyrm.activitystreams.ActivityStream.remove_user_statuses"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        views.inbox.activity_task(activity)
        block = models.UserBlocks.objects.get()
        self.assertEqual(block.user_subject, self.remote_user)
        self.assertEqual(block.user_object, self.local_user)
        self.assertEqual(block.remote_id, "https://example.com/9e1f41ac-9ddd-4159")

        self.assertFalse(models.UserFollows.objects.exists())
        self.assertFalse(models.UserFollowRequest.objects.exists())

    def test_handle_unblock(self):
        """ unblock a user """
        self.remote_user.blocks.add(self.local_user)

        block = models.UserBlocks.objects.get()
        block.remote_id = "https://example.com/9e1f41ac-9ddd-4159"
        block.save()

        self.assertEqual(block.user_subject, self.remote_user)
        self.assertEqual(block.user_object, self.local_user)
        activity = {
            "type": "Undo",
            "actor": "hi",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "object": {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": "https://example.com/9e1f41ac-9ddd-4159",
                "type": "Block",
                "actor": "https://example.com/users/rat",
                "object": "https://example.com/user/mouse",
            },
        }
        with patch(
            "bookwyrm.activitystreams.ActivityStream.add_user_statuses"
        ) as redis_mock:
            views.inbox.activity_task(activity)
            self.assertTrue(redis_mock.called)
        self.assertFalse(models.UserBlocks.objects.exists())
