"""Readwise integration helpers."""

import logging
import re
from html import unescape

import requests
from django.utils.html import strip_tags

from bookwyrm import models, settings
from bookwyrm.models.readthrough import ProgressMode
from bookwyrm.tasks import app, MISC

logger = logging.getLogger(__name__)

READWISE_HIGHLIGHTS_URL = "https://readwise.io/api/v2/highlights/"
READWISE_SOURCE_TYPE = "bookwyrm"


def _clean_text(value):
    value = unescape(strip_tags(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value, length):
    if not value:
        return value
    return value[:length]


def _page_location(quotation):
    if quotation.position_mode != ProgressMode.PAGE or not quotation.position:
        return None
    try:
        return int(quotation.position)
    except (TypeError, ValueError):
        return None


def build_readwise_highlight(quotation):
    """Convert a BookWyrm quotation to a Readwise highlight payload item."""
    highlight = {
        "text": _truncate(_clean_text(quotation.raw_quote or quotation.quote), 8191),
        "title": _truncate(quotation.book.title, 511),
        "source_type": READWISE_SOURCE_TYPE,
        "category": "books",
        "source_url": _truncate(quotation.book.remote_id, 2047),
        "highlight_url": _truncate(
            quotation.remote_id or quotation.get_remote_id(), 4095
        ),
        "highlighted_at": quotation.published_date.isoformat(),
    }

    if author := _clean_text(quotation.book.author_text):
        highlight["author"] = _truncate(author, 1024)

    if note := _clean_text(quotation.raw_content or quotation.content):
        highlight["note"] = _truncate(note, 8191)

    if location := _page_location(quotation):
        highlight["location_type"] = "page"
        highlight["location"] = location

    return highlight


@app.task(queue=MISC)
def sync_readwise_quotation(quotation_id):
    """Send a quotation to Readwise for users who configured a token."""
    quotation = (
        models.Quotation.objects.select_related("user", "book")
        .prefetch_related("book__authors")
        .get(id=quotation_id)
    )

    token = quotation.user.readwise_api_key
    if not token or quotation.deleted:
        return None

    highlight = build_readwise_highlight(quotation)
    if not highlight["text"]:
        return None

    try:
        response = requests.post(
            READWISE_HIGHLIGHTS_URL,
            headers={
                "Authorization": f"Token {token}",
                "User-Agent": settings.USER_AGENT,
            },
            json={"highlights": [highlight]},
            timeout=settings.QUERY_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        logger.warning("Unable to sync quotation %s to Readwise: %s", quotation_id, err)
        return None

    return response.json()
