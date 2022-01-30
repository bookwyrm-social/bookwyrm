""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class Link(TestCase):
    """some activitypub oddness ahead"""

    def setUp(self):
        """look, a list"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )
        work = models.Work.objects.create(title="hello")
        self.book = models.Edition.objects.create(title="hi", parent_work=work)

    def test_create_domain(self, _):
        """generated default name"""
        domain = models.LinkDomain.objects.create(domain="beep.com")
        self.assertEqual(domain.name, "beep.com")
        self.assertEqual(domain.status, "pending")

    def test_create_link_new_domain(self, _):
        """generates link and sets domain"""
        link = models.Link.objects.create(url="https://www.hello.com/hi-there")
        self.assertEqual(link.domain.domain, "www.hello.com")
        self.assertEqual(link.name, "www.hello.com")

    def test_create_link_existing_domain(self, _):
        """generate link with a known domain"""
        domain = models.LinkDomain.objects.create(domain="www.hello.com", name="Hi")

        link = models.Link.objects.create(url="https://www.hello.com/hi-there")
        self.assertEqual(link.domain, domain)
        self.assertEqual(link.name, "Hi")
