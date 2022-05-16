"""test author serializer"""
from django.test import TestCase
from bookwyrm import models


class Author(TestCase):
    """serialize author tests"""

    def setUp(self):
        """initial data"""
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        self.author = models.Author.objects.create(
            name="Author fullname",
            aliases=["One", "Two"],
            bio="bio bio bio",
        )

    def test_serialize_model(self):
        """check presense of author fields"""
        activity = self.author.to_activity()
        self.assertEqual(activity["id"], self.author.remote_id)
        self.assertIsInstance(activity["aliases"], list)
        self.assertEqual(activity["aliases"], ["One", "Two"])
        self.assertEqual(activity["name"], "Author fullname")
