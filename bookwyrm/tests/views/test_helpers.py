""" test for app action functionality """
import json
from unittest.mock import patch
import pathlib
from django.db.models import Q
from django.http import Http404
from django.test import TestCase
from django.test.client import RequestFactory
import responses

from bookwyrm import models, views
from bookwyrm.settings import USER_AGENT


@patch("bookwyrm.activitystreams.ActivityStream.add_status")
class ViewsHelpers(TestCase):
    """viewing and creating statuses"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            discoverable=True,
            localname="mouse",
            remote_id="https://example.com/users/mouse",
        )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Test Book",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                discoverable=True,
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        self.userdata = json.loads(datafile.read_bytes())
        del self.userdata["icon"]
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            self.shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=self.local_user
            )

    def test_get_edition(self, _):
        """given an edition or a work, returns an edition"""
        self.assertEqual(views.helpers.get_edition(self.book.id), self.book)
        self.assertEqual(views.helpers.get_edition(self.work.id), self.book)

    def test_get_user_from_username(self, _):
        """works for either localname or username"""
        self.assertEqual(
            views.helpers.get_user_from_username(self.local_user, "mouse"),
            self.local_user,
        )
        self.assertEqual(
            views.helpers.get_user_from_username(self.local_user, "mouse@local.com"),
            self.local_user,
        )
        with self.assertRaises(Http404):
            views.helpers.get_user_from_username(self.local_user, "mojfse@example.com")

    def test_is_api_request(self, _):
        """should it return html or json"""
        request = self.factory.get("/path")
        request.headers = {"Accept": "application/json"}
        self.assertTrue(views.helpers.is_api_request(request))

        request = self.factory.get("/path.json")
        request.headers = {"Accept": "Praise"}
        self.assertTrue(views.helpers.is_api_request(request))

        request = self.factory.get("/path")
        request.headers = {"Accept": "Praise"}
        self.assertFalse(views.helpers.is_api_request(request))

    def test_is_api_request_no_headers(self, _):
        """should it return html or json"""
        request = self.factory.get("/path")
        self.assertFalse(views.helpers.is_api_request(request))

    def test_is_bookwyrm_request(self, _):
        """checks if a request came from a bookwyrm instance"""
        request = self.factory.get("", {"q": "Test Book"})
        self.assertFalse(views.helpers.is_bookwyrm_request(request))

        request = self.factory.get(
            "",
            {"q": "Test Book"},
            HTTP_USER_AGENT="http.rb/4.4.1 (Mastodon/3.3.0; +https://mastodon.social/)",
        )
        self.assertFalse(views.helpers.is_bookwyrm_request(request))

        request = self.factory.get("", {"q": "Test Book"}, HTTP_USER_AGENT=USER_AGENT)
        self.assertTrue(views.helpers.is_bookwyrm_request(request))

    def test_existing_user(self, _):
        """simple database lookup by username"""
        result = views.helpers.handle_remote_webfinger("@mouse@local.com")
        self.assertEqual(result, self.local_user)

        result = views.helpers.handle_remote_webfinger("mouse@local.com")
        self.assertEqual(result, self.local_user)

        result = views.helpers.handle_remote_webfinger("mOuSe@loCal.cOm")
        self.assertEqual(result, self.local_user)

    @responses.activate
    def test_load_user(self, _):
        """find a remote user using webfinger"""
        username = "mouse@example.com"
        wellknown = {
            "subject": "acct:mouse@example.com",
            "links": [
                {
                    "rel": "self",
                    "type": "application/activity+json",
                    "href": "https://example.com/user/mouse",
                }
            ],
        }
        responses.add(
            responses.GET,
            "https://example.com/.well-known/webfinger?resource=acct:%s" % username,
            json=wellknown,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://example.com/user/mouse",
            json=self.userdata,
            status=200,
        )
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            result = views.helpers.handle_remote_webfinger("@mouse@example.com")
            self.assertIsInstance(result, models.User)
            self.assertEqual(result.username, "mouse@example.com")

    def test_user_on_blocked_server(self, _):
        """find a remote user using webfinger"""
        models.FederatedServer.objects.create(
            server_name="example.com", status="blocked"
        )

        result = views.helpers.handle_remote_webfinger("@mouse@example.com")
        self.assertIsNone(result)

    def test_handle_reading_status_to_read(self, _):
        """posts shelve activities"""
        shelf = self.local_user.shelf_set.get(identifier="to-read")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.helpers.handle_reading_status(
                self.local_user, shelf, self.book, "public"
            )
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, "wants to read")

    def test_handle_reading_status_reading(self, _):
        """posts shelve activities"""
        shelf = self.local_user.shelf_set.get(identifier="reading")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.helpers.handle_reading_status(
                self.local_user, shelf, self.book, "public"
            )
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, "started reading")

    def test_handle_reading_status_read(self, _):
        """posts shelve activities"""
        shelf = self.local_user.shelf_set.get(identifier="read")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.helpers.handle_reading_status(
                self.local_user, shelf, self.book, "public"
            )
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, "finished reading")

    def test_handle_reading_status_other(self, _):
        """posts shelve activities"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.helpers.handle_reading_status(
                self.local_user, self.shelf, self.book, "public"
            )
        self.assertFalse(models.GeneratedNote.objects.exists())

    def test_get_annotated_users(self, _):
        """list of people you might know"""
        user_1 = models.User.objects.create_user(
            "nutria@local.com",
            "nutria@nutria.com",
            "nutriaword",
            local=True,
            localname="nutria",
            discoverable=True,
        )
        user_2 = models.User.objects.create_user(
            "fish@local.com",
            "fish@fish.com",
            "fishword",
            local=True,
            localname="fish",
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            # 1 shared follow
            self.local_user.following.add(user_2)
            user_1.followers.add(user_2)

            # 1 shared book
            models.ShelfBook.objects.create(
                user=self.local_user,
                book=self.book,
                shelf=self.local_user.shelf_set.first(),
            )
            models.ShelfBook.objects.create(
                user=user_1, book=self.book, shelf=user_1.shelf_set.first()
            )

        result = views.helpers.get_annotated_users(self.local_user)
        self.assertEqual(result.count(), 3)
        self.assertTrue(user_1 in result)
        self.assertFalse(user_2 in result)
        self.assertTrue(self.local_user in result)
        self.assertTrue(self.remote_user in result)

        user_1_annotated = result.get(id=user_1.id)
        self.assertEqual(user_1_annotated.mutuals, 1)
        self.assertEqual(user_1_annotated.shared_books, 1)

        remote_user_annotated = result.get(id=self.remote_user.id)
        self.assertEqual(remote_user_annotated.mutuals, 0)
        self.assertEqual(remote_user_annotated.shared_books, 0)

    def test_get_annotated_users_counts(self, _):
        """correct counting for multiple shared attributed"""
        user_1 = models.User.objects.create_user(
            "nutria@local.com",
            "nutria@nutria.com",
            "nutriaword",
            local=True,
            localname="nutria",
            discoverable=True,
        )
        for i in range(3):
            user = models.User.objects.create_user(
                "{:d}@local.com".format(i),
                "{:d}@nutria.com".format(i),
                "password",
                local=True,
                localname=i,
            )
            user.following.add(user_1)
            user.followers.add(self.local_user)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            for i in range(3):
                book = models.Edition.objects.create(
                    title=i,
                    parent_work=models.Work.objects.create(title=i),
                )
                models.ShelfBook.objects.create(
                    user=self.local_user,
                    book=book,
                    shelf=self.local_user.shelf_set.first(),
                )
                models.ShelfBook.objects.create(
                    user=user_1, book=book, shelf=user_1.shelf_set.first()
                )

        result = views.helpers.get_annotated_users(
            self.local_user,
            ~Q(id=self.local_user.id),
            ~Q(followers=self.local_user),
        )
        self.assertEqual(result.count(), 2)
        user_1_annotated = result.get(id=user_1.id)
        self.assertEqual(user_1_annotated.mutuals, 3)
