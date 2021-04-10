""" test for app action functionality """
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class FederationViews(TestCase):
    """ every response to a get request, html or json """

    def setUp(self):
        """ we need basic test data and mocks """
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        models.SiteSettings.objects.create()

    def test_federation_page(self):
        """ there are so many views, this just makes sure it LOADS """
        view = views.Federation.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_server_page(self):
        """ there are so many views, this just makes sure it LOADS """
        server = models.FederatedServer.objects.create(server_name="hi.there.com")
        view = views.FederatedServer.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request, server.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_server_page_post(self):
        """ block and unblock a server """
        server = models.FederatedServer.objects.create(server_name="hi.there.com")
        self.assertEqual(server.status, "federated")

        view = views.FederatedServer.as_view()
        request = self.factory.post("")
        request.user = self.local_user
        request.user.is_superuser = True

        view(request, server.id)
        server.refresh_from_db()
        self.assertEqual(server.status, "blocked")

        view(request, server.id)
        server.refresh_from_db()
        self.assertEqual(server.status, "federated")

    def test_edit_view_get(self):
        """ there are so many views, this just makes sure it LOADS """
        # create mode
        view = views.EditFederatedServer.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request, server=None)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        # edit mode
        server = models.FederatedServer.objects.create(server_name="hi.there.com")
        result = view(request, server=server.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
