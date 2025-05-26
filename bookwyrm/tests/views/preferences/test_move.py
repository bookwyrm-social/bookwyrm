""" test move functionality """
import json
from unittest.mock import patch
import pathlib
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.test.client import RequestFactory
import responses

from bookwyrm import forms, models, views


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.suggested_users.rerank_user_task.delay")
class ViewsHelpers(TestCase):
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
                "rat",
                "rat@rat.com",
                "ratword",
                local=True,
                discoverable=True,
                localname="rat",
            )

        with (
            patch("bookwyrm.models.user.set_remote_server.delay"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
        ):
            cls.remote_user = models.User.objects.create_user(
                "mouse@example.com",
                "mouse@mouse.com",
                "mouseword",
                local=False,
                remote_id="https://example.com/user/mouse",
            )

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        datafile = pathlib.Path(__file__).parent.joinpath(
            "../../data/ap_user_move.json"
        )
        self.userdata = json.loads(datafile.read_bytes())
        del self.userdata["icon"]

    @responses.activate
    @patch("bookwyrm.models.user.set_remote_server.delay")
    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    def test_move_user_view(self, *_):
        """move user"""

        self.assertEqual(self.remote_user.remote_id, "https://example.com/user/mouse")
        self.assertIsNone(self.local_user.moved_to)
        self.assertIsNone(self.remote_user.moved_to)
        self.assertIsNone(self.local_user.also_known_as.first())
        self.assertIsNone(self.remote_user.also_known_as.first())

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

        responses.add(
            responses.GET,
            "https://your.domain.here:4242/user/rat",
            json=self.local_user.to_activity(),
            status=200,
        )

        view = views.MoveUser.as_view()
        form = forms.MoveUserForm()
        form.data["target"] = "mouse@example.com"
        form.data["password"] = "ratword"

        request = self.factory.post("", form.data)
        request.user = self.local_user
        middleware = SessionMiddleware(request)
        middleware.process_request(request)
        request.session.save()

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request)
            self.local_user.refresh_from_db()

            self.assertEqual(self.local_user.also_known_as.first(), self.remote_user)
            self.assertEqual(self.remote_user.also_known_as.first(), self.local_user)
            self.assertEqual(self.local_user.moved_to, "https://example.com/user/mouse")
