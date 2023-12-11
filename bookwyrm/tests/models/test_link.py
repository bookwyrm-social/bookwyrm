""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class Link(TestCase):
    """some activitypub oddness ahead"""

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
