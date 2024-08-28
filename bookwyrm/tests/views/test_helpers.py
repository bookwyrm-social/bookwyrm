""" test for app action functionality """
import json
from unittest.mock import patch
import pathlib
from django.http import Http404
from django.test import TestCase
from django.test.client import RequestFactory
import responses

from bookwyrm import models, views
from bookwyrm.settings import USER_AGENT, BASE_URL


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.suggested_users.rerank_user_task.delay")
class ViewsHelpers(TestCase):  # pylint: disable=too-many-public-methods
    """viewing and creating statuses"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                discoverable=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        with (
            patch("bookwyrm.models.user.set_remote_server.delay"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
        ):
            cls.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                discoverable=True,
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        cls.work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Test Book",
            remote_id="https://example.com/book/1",
            parent_work=cls.work,
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            cls.shelf = models.Shelf.objects.create(
                name="Test Shelf", identifier="test-shelf", user=cls.local_user
            )

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        self.userdata = json.loads(datafile.read_bytes())
        del self.userdata["icon"]

    def test_get_edition(self, *_):
        """given an edition or a work, returns an edition"""
        self.assertEqual(views.helpers.get_edition(self.book.id), self.book)
        self.assertEqual(views.helpers.get_edition(self.work.id), self.book)

    def test_get_user_from_username(self, *_):
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

    def test_is_api_request(self, *_):
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

    def test_is_api_request_no_headers(self, *_):
        """should it return html or json"""
        request = self.factory.get("/path")
        self.assertFalse(views.helpers.is_api_request(request))

    def test_is_bookwyrm_request(self, *_):
        """checks if a request came from a bookwyrm instance"""
        request = self.factory.get("", {"q": "Test Book"})
        self.assertFalse(views.helpers.is_bookwyrm_request(request))

        request = self.factory.get(
            "",
            {"q": "Test Book"},
            headers={
                # pylint: disable-next=line-too-long
                "user-agent": "http.rb/4.4.1 (Mastodon/3.3.0; +https://mastodon.social/)",
            },
        )
        self.assertFalse(views.helpers.is_bookwyrm_request(request))

        request = self.factory.get(
            "",
            {"q": "Test Book"},
            headers={
                "user-agent": USER_AGENT,
            },
        )
        self.assertTrue(views.helpers.is_bookwyrm_request(request))

    def test_handle_remote_webfinger_invalid(self, *_):
        """Various ways you can send a bad query"""
        # if there's no query, there's no result
        result = views.helpers.handle_remote_webfinger(None)
        self.assertIsNone(result)

        # malformed user
        result = views.helpers.handle_remote_webfinger("noatsymbol")
        self.assertIsNone(result)

    def test_handle_remote_webfinger_existing_user(self, *_):
        """simple database lookup by username"""
        result = views.helpers.handle_remote_webfinger("@mouse@local.com")
        self.assertEqual(result, self.local_user)

        result = views.helpers.handle_remote_webfinger("mouse@local.com")
        self.assertEqual(result, self.local_user)

        result = views.helpers.handle_remote_webfinger("mOuSe@loCal.cOm")
        self.assertEqual(result, self.local_user)

    @responses.activate
    def test_handle_remote_webfinger_load_user_invalid_result(self, *_):
        """find a remote user using webfinger, but fail"""
        username = "mouse@example.com"
        responses.add(
            responses.GET,
            f"https://example.com/.well-known/webfinger?resource=acct:{username}",
            status=500,
        )
        result = views.helpers.handle_remote_webfinger("@mouse@example.com")
        self.assertIsNone(result)

    @responses.activate
    def test_handle_remote_webfinger_load_user(self, *_):
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
            f"https://example.com/.well-known/webfinger?resource=acct:{username}",
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

    def test_handler_remote_webfinger_user_on_blocked_server(self, *_):
        """find a remote user using webfinger"""
        models.FederatedServer.objects.create(
            server_name="example.com", status="blocked"
        )

        result = views.helpers.handle_remote_webfinger("@mouse@example.com")
        self.assertIsNone(result)

    @responses.activate
    def test_subscribe_remote_webfinger(self, *_):
        """remote subscribe templates"""
        query = "mouse@example.com"
        response = {
            "subject": f"acct:{query}",
            "links": [
                {
                    "rel": "self",
                    "type": "application/activity+json",
                    "href": "https://example.com/user/mouse",
                    "template": "hi",
                },
                {
                    "rel": "http://ostatus.org/schema/1.0/subscribe",
                    "type": "application/activity+json",
                    "href": "https://example.com/user/mouse",
                    "template": "hello",
                },
            ],
        }
        responses.add(
            responses.GET,
            f"https://example.com/.well-known/webfinger?resource=acct:{query}",
            json=response,
            status=200,
        )
        template = views.helpers.subscribe_remote_webfinger(query)
        self.assertEqual(template, "hello")
        template = views.helpers.subscribe_remote_webfinger(f"@{query}")
        self.assertEqual(template, "hello")

    def test_handle_reading_status_to_read(self, *_):
        """posts shelve activities"""
        shelf = self.local_user.shelf_set.get(identifier="to-read")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.helpers.handle_reading_status(
                self.local_user, shelf, self.book, "public"
            )
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, "wants to read")

    def test_handle_reading_status_reading(self, *_):
        """posts shelve activities"""
        shelf = self.local_user.shelf_set.get(identifier="reading")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.helpers.handle_reading_status(
                self.local_user, shelf, self.book, "public"
            )
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, "started reading")

    def test_handle_reading_status_read(self, *_):
        """posts shelve activities"""
        shelf = self.local_user.shelf_set.get(identifier="read")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.helpers.handle_reading_status(
                self.local_user, shelf, self.book, "public"
            )
        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.mention_books.first(), self.book)
        self.assertEqual(status.content, "finished reading")

    def test_handle_reading_status_other(self, *_):
        """posts shelve activities"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            views.helpers.handle_reading_status(
                self.local_user, self.shelf, self.book, "public"
            )
        self.assertFalse(models.GeneratedNote.objects.exists())

    def test_redirect_to_referer_outside_domain(self, *_):
        """safely send people on their way"""
        request = self.factory.get(
            "/path",
            headers={
                "referer": "http://outside.domain/name",
            },
        )
        result = views.helpers.redirect_to_referer(
            request, "user-feed", self.local_user.localname
        )
        self.assertEqual(result.url, f"/user/{self.local_user.localname}")

    def test_redirect_to_referer_outside_domain_with_fallback(self, *_):
        """invalid domain with regular params for the redirect function"""
        request = self.factory.get(
            "/path",
            headers={
                "referer": "http://outside.domain/name",
            },
        )
        result = views.helpers.redirect_to_referer(request)
        self.assertEqual(result.url, "/")

    def test_redirect_to_referer_valid_domain(self, *_):
        """redirect to within the app"""
        request = self.factory.get(
            "/path",
            headers={
                "referer": f"{BASE_URL}/and/a/path",
            },
        )
        result = views.helpers.redirect_to_referer(request)
        self.assertEqual(result.url, f"{BASE_URL}/and/a/path")

    def test_redirect_to_referer_with_get_args(self, *_):
        """if the path has get params (like sort) they are preserved"""
        request = self.factory.get(
            "/path",
            headers={
                "referer": f"{BASE_URL}/and/a/path?sort=hello",
            },
        )
        result = views.helpers.redirect_to_referer(request)
        self.assertEqual(result.url, f"{BASE_URL}/and/a/path?sort=hello")
