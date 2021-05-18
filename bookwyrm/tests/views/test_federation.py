""" test for app action functionality """
import json
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


class FederationViews(TestCase):
    """every response to a get request, html or json"""

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
        """there are so many views, this just makes sure it LOADS"""
        view = views.Federation.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_server_page(self):
        """there are so many views, this just makes sure it LOADS"""
        server = models.FederatedServer.objects.create(server_name="hi.there.com")
        view = views.FederatedServer.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request, server.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_server_page_block(self):
        """block a server"""
        server = models.FederatedServer.objects.create(
            server_name="hi.there.com", application_type="bookwyrm"
        )
        connector = models.Connector.objects.get(
            identifier="hi.there.com",
        )
        self.remote_user.federated_server = server
        self.remote_user.save()

        self.assertEqual(server.status, "federated")

        view = views.federation.block_server
        request = self.factory.post("")
        request.user = self.local_user
        request.user.is_superuser = True

        view(request, server.id)

        server.refresh_from_db()
        self.remote_user.refresh_from_db()
        self.assertEqual(server.status, "blocked")

        # and the user was deactivated
        self.assertFalse(self.remote_user.is_active)
        self.assertEqual(self.remote_user.deactivation_reason, "domain_block")

        # and the connector was disabled
        connector.refresh_from_db()
        self.assertFalse(connector.active)
        self.assertEqual(connector.deactivation_reason, "domain_block")

    def test_server_page_unblock(self):
        """unblock a server"""
        server = models.FederatedServer.objects.create(
            server_name="hi.there.com", status="blocked", application_type="bookwyrm"
        )
        connector = models.Connector.objects.get(
            identifier="hi.there.com",
        )
        connector.active = False
        connector.deactivation_reason = "domain_block"
        connector.save()

        self.remote_user.federated_server = server
        self.remote_user.is_active = False
        self.remote_user.deactivation_reason = "domain_block"
        self.remote_user.save()

        request = self.factory.post("")
        request.user = self.local_user
        request.user.is_superuser = True

        views.federation.unblock_server(request, server.id)
        server.refresh_from_db()
        self.remote_user.refresh_from_db()
        self.assertEqual(server.status, "federated")

        # and the user was re-activated
        self.assertTrue(self.remote_user.is_active)
        self.assertIsNone(self.remote_user.deactivation_reason)

        # and the connector was re-enabled
        connector.refresh_from_db()
        self.assertTrue(connector.active)
        self.assertIsNone(connector.deactivation_reason)

    def test_add_view_get(self):
        """there are so many views, this just makes sure it LOADS"""
        # create mode
        view = views.AddFederatedServer.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_add_view_post_create(self):
        """create a server entry"""
        form = forms.ServerForm()
        form.data["server_name"] = "remote.server"
        form.data["application_type"] = "coolsoft"
        form.data["status"] = "blocked"

        view = views.AddFederatedServer.as_view()
        request = self.factory.post("", form.data)
        request.user = self.local_user
        request.user.is_superuser = True

        view(request)
        server = models.FederatedServer.objects.get()
        self.assertEqual(server.server_name, "remote.server")
        self.assertEqual(server.application_type, "coolsoft")
        self.assertEqual(server.status, "blocked")

    def test_import_blocklist(self):
        """load a json file with a list of servers to block"""
        server = models.FederatedServer.objects.create(server_name="hi.there.com")
        self.remote_user.federated_server = server
        self.remote_user.save()

        data = [
            {"instance": "server.name", "url": "https://explanation.url"},  # new server
            {"instance": "hi.there.com", "url": "https://explanation.url"},  # existing
            {"a": "b"},  # invalid
        ]
        json.dump(data, open("file.json", "w"))

        view = views.ImportServerBlocklist.as_view()
        request = self.factory.post(
            "",
            {
                "json_file": SimpleUploadedFile(
                    "file.json", open("file.json", "rb").read()
                )
            },
        )
        request.user = self.local_user
        request.user.is_superuser = True

        view(request)
        server.refresh_from_db()
        self.remote_user.refresh_from_db()

        self.assertEqual(models.FederatedServer.objects.count(), 2)
        self.assertEqual(server.status, "blocked")
        self.assertFalse(self.remote_user.is_active)
        created = models.FederatedServer.objects.get(server_name="server.name")
        self.assertEqual(created.status, "blocked")
        self.assertEqual(created.notes, "https://explanation.url")
