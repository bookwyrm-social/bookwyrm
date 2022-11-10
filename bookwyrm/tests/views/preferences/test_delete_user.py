""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


@patch("bookwyrm.suggested_users.remove_user_task.delay")
class DeleteUserViews(TestCase):
    """view user and edit profile"""

    # pylint: disable=invalid-name
    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@your.domain.here",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
            self.rat = models.User.objects.create_user(
                "rat@your.domain.here",
                "rat@rat.rat",
                "password",
                local=True,
                localname="rat",
            )

            self.book = models.Edition.objects.create(
                title="test", parent_work=models.Work.objects.create(title="test work")
            )
            with patch(
                "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
            ), patch("bookwyrm.activitystreams.add_book_statuses_task.delay"):
                models.ShelfBook.objects.create(
                    book=self.book,
                    user=self.local_user,
                    shelf=self.local_user.shelf_set.first(),
                )

        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_delete_user_page(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DeleteUser.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.suggested_users.rerank_suggestions_task")
    def test_delete_user(self, *_):
        """use a form to update a user"""
        view = views.DeleteUser.as_view()
        form = forms.DeleteUserForm()
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.local_user
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()

        self.assertIsNone(self.local_user.name)
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as delay_mock:
            view(request)
        self.assertEqual(delay_mock.call_count, 1)
        activity = json.loads(delay_mock.call_args[1]["args"][1])
        self.assertEqual(activity["type"], "Delete")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(
            activity["cc"][0], "https://www.w3.org/ns/activitystreams#Public"
        )

        self.local_user.refresh_from_db()
        self.assertFalse(self.local_user.is_active)
        self.assertEqual(self.local_user.deactivation_reason, "self_deletion")

    def test_deactivate_user(self, _):
        """Impermanent deletion"""
        self.assertTrue(self.local_user.is_active)
        view = views.DeactivateUser.as_view()
        request = self.factory.post("")
        request.user = self.local_user
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()

        view(request)

        self.local_user.refresh_from_db()
        self.assertFalse(self.local_user.is_active)
        self.assertEqual(self.local_user.deactivation_reason, "self_deactivation")

    def test_reactivate_user_get(self, _):
        """Reactication page"""
        view = views.ReactivateUser.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_reactivate_user_post(self, _):
        """Reactivate action"""
        self.local_user.deactivate()
        self.local_user.refresh_from_db()

        view = views.ReactivateUser.as_view()
        form = forms.LoginForm()
        form.data["localname"] = "mouse"
        form.data["password"] = "password"
        request = self.factory.post("", form.data)
        request.user = self.local_user
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()

        with patch("bookwyrm.views.preferences.delete_user.login"):
            view(request)

        self.local_user.refresh_from_db()
        self.assertTrue(self.local_user.is_active)
        self.assertIsNone(self.local_user.deactivation_reason)
