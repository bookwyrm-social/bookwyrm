"""test security middleware"""

from django.test import Client, TestCase
from bookwyrm.settings import DOMAIN

from bookwyrm import models


class TestBookWyrmSecurityChecks(TestCase):
    """lets get fuzzing"""

    @classmethod
    def setUpTestData(cls):
        """create users and test data"""

        cls.user = models.User.objects.create_user(
            f"mouse@{DOMAIN}",
            "mouse@example.com",
            "",
            local=True,
            localname="mouse",
        )

        cls.site = models.SiteSettings.get()

    def test_require_login_everywhere(self):
        """is search page blocked"""

        self.site.require_login_everywhere = False
        c = Client()
        response = c.get("/user/mouse")
        self.assertEqual(response.status_code, 200)

        self.site.require_login_everywhere = True
        c = Client()
        response = c.get("/user/mouse")
        self.assertEqual(response.status_code, 403)
