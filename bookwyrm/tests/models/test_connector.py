""" testing connector model """

import pytest
from django.test import TestCase
from bookwyrm import models


class Connector(TestCase):
    """do the connector functions work?"""

    def setUp(self):
        """we'll need a connector"""

        models.Connector.objects.create(
            identifier="bookwyrm.social",
            name="Bookwyrm.social",
            connector_file="bookwyrm_connector",
            base_url="https://bookwyrm.social",
            books_url="https://bookwyrm.social/book",
            covers_url="https://bookwyrm.social/images/",
            search_url="https://bookwyrm.social/search?q=",
            isbn_search_url="https://bookwyrm.social/isbn/",
            priority=2,
        )

    def test_deactivate(self):
        """test we can deactivate connectors"""

        connector = models.Connector.objects.all().last()
        self.assertEqual(True, connector.active)
        connector.deactivate("testing")
        self.assertEqual(False, connector.active)
        self.assertEqual("testing", connector.deactivation_reason)

    def test_activate(self):
        """test we can activate connectors"""

        connector = models.Connector.objects.all().last()
        connector.active = False
        connector.save()
        self.assertEqual(False, connector.active)
        connector.activate()
        self.assertEqual(True, connector.active)
        self.assertEqual(None, connector.deactivation_reason)

    def test_change_priority(self) -> None:
        """Test change the priority value for a connector"""

        connector = models.Connector.objects.all().last()
        self.assertEqual(2, connector.priority)
        connector.change_priority(99)
        self.assertEqual(99, connector.priority)

    pytest.mark.skip("Function reserved for future use.")

    def test_update(self) -> None:
        """Test update the settings for this connector. e.g. if the
        API endpoints change."""
