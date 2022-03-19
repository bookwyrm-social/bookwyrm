""" test for app action functionality """
from unittest.mock import patch

from django.http import StreamingHttpResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class ExportViews(TestCase):
    """viewing and creating statuses"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Test Book",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
            isbn_13="9781234567890",
            bnf_id="beep",
        )

    def test_export(self, *_):
        """simple export"""
        models.ShelfBook.objects.create(
            shelf=self.local_user.shelf_set.first(),
            user=self.local_user,
            book=self.book,
        )
        request = self.factory.get("")
        request.user = self.local_user
        export = views.export_user_book_data(request)
        self.assertIsInstance(export, StreamingHttpResponse)
        self.assertEqual(export.status_code, 200)
        result = list(export.streaming_content)
        # pylint: disable=line-too-long
        self.assertEqual(
            result[0],
            b"title,remote_id,openlibrary_key,inventaire_id,librarything_key,goodreads_key,bnf_id,viaf,wikidata,asin,isbn_10,isbn_13,oclc_number\r\n",
        )
        expected = f"Test Book,{self.book.remote_id},,,,,beep,,,,123456789X,9781234567890,\r\n"
        self.assertEqual(
            result[1].decode("utf-8"),
            expected
        )
