""" test for app action functionality """
from unittest.mock import patch
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


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
        self.remote_user.federated_server = server
        self.remote_user.save()

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

    def test_add_view_get(self):
        """ there are so many views, this just makes sure it LOADS """
        # create mode
        view = views.AddFederatedServer.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request, server=None)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_add_view_post_create(self):
        """ create or edit a server """
        form = forms.ServerForm()
        form.data["server_name"] = "remote.server"
        form.data["software"] = "coolsoft"

        view = views.AddFederatedServer.as_view()
        request = self.factory.post("", form.data)
        request.user = self.local_user
        request.user.is_superuser = True

        view(request, server=None)
        server = models.FederatedServer.objects.get()
        self.assertEqual(server.server_name, "remote.server")
        self.assertEqual(server.software, "coolsoft")
        self.assertEqual(server.status, "federated")
