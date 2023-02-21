""" tests functionality specifically for the Note ActivityPub dataclass"""
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import activitypub
from bookwyrm import models


class Note(TestCase):
    """the model-linked ActivityPub dataclass for Note-based types"""

    # pylint: disable=invalid-name
    def setUp(self):
        """create a shared user"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )
        self.user.remote_id = "https://test-instance.org/user/critic"
        self.user.save(broadcast=False, update_fields=["remote_id"])

        self.book = models.Edition.objects.create(
            title="Test Edition", remote_id="http://book.com/book"
        )

    def test_to_model_hashtag_postprocess_content(self):
        """test that hashtag links are post-processed and link to local URLs"""
        update_data = activitypub.Comment(
            id="https://test-instance.org/user/critic/comment/42",
            attributedTo=self.user.remote_id,
            inReplyToBook=self.book.remote_id,
            content="<p>This is interesting "
            + '<a href="https://test-instance.org/hashtag/2" data-mention="hashtag">'
            + "#bookclub</a></p>",
            published="2023-02-17T23:12:59.398030+00:00",
            to=[],
            cc=[],
            tag=[
                {
                    "type": "Edition",
                    "name": "gerald j. books",
                    "href": "http://book.com/book",
                },
                {
                    "type": "Hashtag",
                    "name": "#BookClub",
                    "href": "https://test-instance.org/hashtag/2",
                },
            ],
        )

        instance = update_data.to_model(model=models.Status)
        self.assertIsNotNone(instance)
        hashtag = models.Hashtag.objects.filter(name="#BookClub").first()
        self.assertIsNotNone(hashtag)
        self.assertEqual(
            instance.content,
            "<p>This is interesting "
            + f'<a href="{hashtag.remote_id}" data-mention="hashtag">'
            + "#bookclub</a></p>",
        )
