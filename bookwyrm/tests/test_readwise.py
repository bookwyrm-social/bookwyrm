"""Readwise integration tests."""

import json
from unittest.mock import patch

import responses
from django.test import TestCase

from bookwyrm import models
from bookwyrm.models.readthrough import ProgressMode
from bookwyrm.readwise import (
    READWISE_HIGHLIGHTS_URL,
    build_readwise_highlight,
    sync_readwise_quotation,
)


class Readwise(TestCase):
    """sending BookWyrm quotes to Readwise"""

    @classmethod
    def setUpTestData(cls):
        """model objects we'll need"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
                readwise_api_key="readwise-token",
            )
        cls.author = models.Author.objects.create(name="Octavia Butler")
        cls.work = models.Work.objects.create(title="Example Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=cls.work,
        )
        cls.book.authors.add(cls.author)

    def create_quotation(self):
        """create a quotation without exercising broadcast tasks"""
        with (
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.activitystreams.add_status_task.apply_async"),
        ):
            return models.Quotation.objects.create(
                user=self.user,
                book=self.book,
                quote="<p>There is nothing new under the sun.</p>",
                raw_quote="There is nothing new under the sun.",
                content="<p>Worth remembering.</p>",
                raw_content="Worth remembering.",
                privacy="public",
                position="42",
                position_mode=ProgressMode.PAGE,
            )

    def test_build_readwise_highlight(self):
        """format a BookWyrm quotation for Readwise"""
        quotation = self.create_quotation()

        result = build_readwise_highlight(quotation)

        self.assertEqual(result["text"], "There is nothing new under the sun.")
        self.assertEqual(result["note"], "Worth remembering.")
        self.assertEqual(result["title"], "Example Edition")
        self.assertEqual(result["author"], "Octavia Butler")
        self.assertEqual(result["source_type"], "bookwyrm")
        self.assertEqual(result["category"], "books")
        self.assertEqual(result["source_url"], quotation.book.remote_id)
        self.assertEqual(result["highlight_url"], quotation.remote_id)
        self.assertEqual(result["location_type"], "page")
        self.assertEqual(result["location"], 42)

    @responses.activate
    def test_sync_readwise_quotation(self):
        """post a quotation to Readwise"""
        quotation = self.create_quotation()
        responses.post(
            READWISE_HIGHLIGHTS_URL,
            json=[{"modified_highlights": [123]}],
            status=200,
        )

        result = sync_readwise_quotation(quotation.id)

        self.assertEqual(result, [{"modified_highlights": [123]}])
        self.assertEqual(len(responses.calls), 1)
        request = responses.calls[0].request
        self.assertEqual(request.headers["Authorization"], "Token readwise-token")
        payload = json.loads(request.body)
        self.assertEqual(
            payload["highlights"][0]["text"],
            "There is nothing new under the sun.",
        )

    @responses.activate
    def test_sync_readwise_quotation_without_token(self):
        """do not call Readwise unless a token is configured"""
        self.user.readwise_api_key = ""
        self.user.save(broadcast=False, update_fields=["readwise_api_key"])
        quotation = self.create_quotation()

        result = sync_readwise_quotation(quotation.id)

        self.assertIsNone(result)
        self.assertEqual(len(responses.calls), 0)
