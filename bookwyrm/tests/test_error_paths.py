"""test error pages"""

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from bookwyrm.views.server_error import server_error
from bookwyrm.views.permission_denied import permission_denied


class ErrorPages(TestCase):
    """test custom error pages"""

    def test_500(self):
        """does a server error return a 500"""

        req = RequestFactory().get("/")
        self.assertEqual(server_error(req).status_code, 500)

    def test_403(self):
        """does permission denied error return a 403"""

        req = RequestFactory().get("/")
        self.assertEqual(permission_denied(req, PermissionDenied()).status_code, 403)

    def test_get_404(self):
        """does 404 page return a 404"""

        response = self.client.get("/404/")
        self.assertEqual(response.status_code, 404)

    def test_raise_404(self):
        """does a random non-page return a 404 error"""

        response = self.client.get("/kljdfjasdfasdf")
        self.assertEqual(response.status_code, 404)
