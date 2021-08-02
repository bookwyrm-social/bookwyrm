""" test for app action functionality """
from unittest.mock import patch
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


class GetStartedViews(TestCase):
    """helping new users get oriented"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        self.book = models.Edition.objects.create(
            parent_work=models.Work.objects.create(title="hi"),
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        models.Connector.objects.create(
            identifier="self", connector_file="self_connector", local=True
        )
        models.SiteSettings.objects.create()

    def test_profile_view(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.GetStartedProfile.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_profile_view_post(self):
        """save basic user details"""
        view = views.GetStartedProfile.as_view()
        form = forms.LimitedEditUserForm(instance=self.local_user)
        form.data["name"] = "New Name"
        form.data["discoverable"] = "True"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        self.assertIsNone(self.local_user.name)
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.delay"
        ) as delay_mock:
            view(request)
            self.assertEqual(delay_mock.call_count, 1)
        self.assertEqual(self.local_user.name, "New Name")
        self.assertTrue(self.local_user.discoverable)

    def test_books_view(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.GetStartedBooks.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_books_view_with_query(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.GetStartedBooks.as_view()
        request = self.factory.get("?query=Example")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_books_view_post(self):
        """shelve some books"""
        view = views.GetStartedBooks.as_view()
        data = {self.book.id: self.local_user.shelf_set.first().id}
        request = self.factory.post("", data)
        request.user = self.local_user

        self.assertFalse(self.local_user.shelfbook_set.exists())
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.delay"
        ) as delay_mock:
            view(request)
            self.assertEqual(delay_mock.call_count, 1)

        shelfbook = self.local_user.shelfbook_set.first()
        self.assertEqual(shelfbook.book, self.book)
        self.assertEqual(shelfbook.user, self.local_user)

    def test_users_view(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.GetStartedUsers.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_users_view_with_query(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.GetStartedUsers.as_view()
        request = self.factory.get("?query=rat")
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
