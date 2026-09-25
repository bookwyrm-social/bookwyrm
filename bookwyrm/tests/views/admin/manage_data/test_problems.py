"""test for app action functionality"""

from django.contrib.auth.models import Permission
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.views.admin.manage_data.problems import get_invalid_isbns
from bookwyrm.tests.validate_html import validate_html


class ProblemsViews(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        perm = Permission.objects.get(codename="manage_data")
        cls.local_user.user_permissions.add(perm)

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_problems_get_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DataProblems.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_problems_get_with_data(self):
        """there are so many views, this just makes sure it LOADS"""
        models.Edition.objects.create(title="Bad", isbn_10="123")
        models.Edition.objects.create(title="Bad II", isbn_13="345")

        view = views.DataProblems.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_get_invalid_isbns(self):
        """find books with incorrect isbns"""
        bad_10 = models.Edition.objects.create(title="Bad", isbn_10="123")
        bad_13 = models.Edition.objects.create(title="Bad II", isbn_13="345")
        bad_both = models.Edition.objects.create(
            title="Bad III", isbn_10="a", isbn_13="345"
        )
        fine = models.Edition.objects.create(title="Fine")

        results = get_invalid_isbns()
        self.assertTrue(bad_10 in results)
        self.assertTrue(bad_13 in results)
        self.assertTrue(bad_both in results)
        self.assertFalse(fine in results)
