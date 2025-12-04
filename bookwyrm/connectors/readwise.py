"""Readwise API client and Celery tasks for highlight sync"""

import logging
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from bookwyrm import models
from bookwyrm.connectors import connector_manager
from bookwyrm.tasks import app, CONNECTORS

logger = logging.getLogger(__name__)

# Rate limiting: Readwise allows 240 req/min general, 20/min for list endpoints
REQUEST_DELAY = 0.25  # 250ms between requests (conservative)


class ReadwiseAPIError(Exception):
    """Error communicating with Readwise API"""

    pass


class ReadwiseClient:
    """Client for Readwise API v2"""

    BASE_URL = "https://readwise.io/api/v2/"

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Token {token}"
        self.session.headers["Content-Type"] = "application/json"

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[requests.Response]:
        """Make a request to Readwise API with rate limiting"""
        url = urljoin(self.BASE_URL, endpoint)
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise ReadwiseAPIError("Invalid Readwise API token") from e
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                raise ReadwiseAPIError(
                    f"Rate limited. Retry after {retry_after} seconds"
                ) from e
            raise ReadwiseAPIError(f"Readwise API error: {e}") from e
        except requests.exceptions.RequestException as e:
            raise ReadwiseAPIError(f"Request failed: {e}") from e

    def validate_token(self) -> bool:
        """Validate the API token. Returns True if valid."""
        try:
            response = self._request("GET", "auth/")
            return response.status_code == 204
        except ReadwiseAPIError:
            return False

    def export_highlights(self, updated_after: Optional[datetime] = None) -> list:
        """
        Export highlights from Readwise.
        Only returns books (filters out articles, tweets, podcasts).

        Args:
            updated_after: Only return highlights updated after this time

        Returns:
            List of book objects with their highlights
        """
        books = []
        params = {}
        if updated_after:
            params["updatedAfter"] = updated_after.isoformat()

        next_cursor = None
        while True:
            if next_cursor:
                params["pageCursor"] = next_cursor

            response = self._request("GET", "export/", params=params)
            data = response.json()

            # Filter to only books (exclude articles, tweets, podcasts, etc.)
            for book in data.get("results", []):
                if book.get("category") == "books":
                    books.append(book)

            next_cursor = data.get("nextPageCursor")
            if not next_cursor:
                break

            # Rate limiting
            time.sleep(REQUEST_DELAY)

        return books

    def create_highlights(self, highlights: list) -> dict:
        """
        Create highlights in Readwise.

        Args:
            highlights: List of highlight dicts with required fields:
                - text: The highlight text
                - title: Book title
                Optional fields:
                - author: Book author
                - source_type: Source identifier (e.g., "bookwyrm")
                - source_url: URL to original
                - location: Page number or position
                - location_type: "page", "order", or "time_offset"
                - note: User's note on the highlight
                - highlighted_at: ISO timestamp

        Returns:
            API response dict
        """
        response = self._request("POST", "highlights/", json={"highlights": highlights})
        return response.json()


def _get_or_create_sync(user: models.User) -> models.ReadwiseSync:
    """Get or create ReadwiseSync record for user"""
    sync, _ = models.ReadwiseSync.objects.get_or_create(user=user)
    return sync


def _match_book(title: str, author: str) -> Optional[models.Edition]:
    """
    Try to find a matching book in BookWyrm.

    Args:
        title: Book title from Readwise
        author: Book author from Readwise

    Returns:
        Matched Edition or None
    """
    if not title:
        return None

    # Search using connector_manager
    search_query = f"{title} {author}" if author else title
    results = connector_manager.search(search_query, min_confidence=0.8)

    if results:
        # Return the first result that has an edition
        for result in results:
            if hasattr(result, "edition") and result.edition:
                return result.edition
            # Try to get or create from the result
            try:
                book = result.connector.get_or_create_book(result.key)
                if isinstance(book, models.Edition):
                    return book
                if isinstance(book, models.Work) and book.default_edition:
                    return book.default_edition
            except Exception as e:
                logger.warning(f"Failed to get book from search result: {e}")
                continue

    return None


def _quotation_to_highlight(quotation: models.Quotation) -> dict:
    """Convert a BookWyrm Quotation to Readwise highlight format"""
    highlight = {
        "text": quotation.raw_quote or strip_tags(quotation.quote),
        "title": quotation.book.title,
        "source_type": "bookwyrm",
        "source_url": quotation.remote_id,
        "highlighted_at": quotation.published_date.isoformat(),
    }

    # Add author if available
    if quotation.book.author_text:
        highlight["author"] = quotation.book.author_text

    # Add location/page info
    if quotation.position:
        highlight["location"] = int(quotation.position) if quotation.position.isdigit() else 0
        highlight["location_type"] = "page" if quotation.position_mode == "PG" else "order"

    # Add note (user's commentary on the quote)
    if quotation.content:
        note = strip_tags(quotation.content).strip()
        if note:
            highlight["note"] = note

    return highlight


@app.task(queue=CONNECTORS)
def export_quote_to_readwise(quotation_id: int) -> bool:
    """
    Export a single quote to Readwise.

    Args:
        quotation_id: ID of the Quotation to export

    Returns:
        True if successful, False otherwise
    """
    try:
        quotation = models.Quotation.objects.select_related("user", "book").get(
            id=quotation_id
        )
    except models.Quotation.DoesNotExist:
        logger.error(f"Quotation {quotation_id} not found")
        return False

    user = quotation.user
    if not user.readwise_token:
        logger.warning(f"User {user.username} has no Readwise token")
        return False

    # Skip if already exported
    if quotation.readwise_highlight_id:
        logger.info(f"Quotation {quotation_id} already exported to Readwise")
        return True

    try:
        client = ReadwiseClient(user.readwise_token)
        highlight = _quotation_to_highlight(quotation)
        result = client.create_highlights([highlight])

        # Store the Readwise highlight ID if returned
        if result and result.get("modified_highlights"):
            modified = result["modified_highlights"]
            if modified:
                quotation.readwise_highlight_id = modified[0].get("id")
                quotation.save(update_fields=["readwise_highlight_id"])

        # Update sync timestamp
        sync = _get_or_create_sync(user)
        sync.mark_export()

        logger.info(f"Exported quotation {quotation_id} to Readwise")
        return True

    except ReadwiseAPIError as e:
        logger.error(f"Failed to export quotation {quotation_id}: {e}")
        return False


@app.task(queue=CONNECTORS)
def export_all_quotes_to_readwise(user_id: int) -> dict:
    """
    Export all unexported quotes for a user to Readwise.

    Args:
        user_id: ID of the User

    Returns:
        Dict with export statistics
    """
    try:
        user = models.User.objects.get(id=user_id)
    except models.User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {"error": "User not found"}

    if not user.readwise_token:
        return {"error": "No Readwise token configured"}

    # Get all unexported quotations
    quotations = models.Quotation.objects.filter(
        user=user,
        deleted=False,
        readwise_highlight_id__isnull=True,
    ).select_related("book")

    if not quotations.exists():
        return {"exported": 0, "message": "No quotes to export"}

    client = ReadwiseClient(user.readwise_token)
    exported = 0
    failed = 0

    # Batch export (Readwise accepts multiple highlights)
    batch_size = 100
    highlights_batch = []
    quotation_ids = []

    for quotation in quotations:
        highlight = _quotation_to_highlight(quotation)
        highlights_batch.append(highlight)
        quotation_ids.append(quotation.id)

        if len(highlights_batch) >= batch_size:
            try:
                result = client.create_highlights(highlights_batch)
                if result.get("modified_highlights"):
                    # Update quotations with Readwise IDs
                    for i, modified in enumerate(result["modified_highlights"]):
                        if i < len(quotation_ids):
                            models.Quotation.objects.filter(id=quotation_ids[i]).update(
                                readwise_highlight_id=modified.get("id")
                            )
                    exported += len(result["modified_highlights"])
            except ReadwiseAPIError as e:
                logger.error(f"Batch export failed: {e}")
                failed += len(highlights_batch)

            highlights_batch = []
            quotation_ids = []
            time.sleep(REQUEST_DELAY)

    # Export remaining highlights
    if highlights_batch:
        try:
            result = client.create_highlights(highlights_batch)
            if result.get("modified_highlights"):
                for i, modified in enumerate(result["modified_highlights"]):
                    if i < len(quotation_ids):
                        models.Quotation.objects.filter(id=quotation_ids[i]).update(
                            readwise_highlight_id=modified.get("id")
                        )
                exported += len(result["modified_highlights"])
        except ReadwiseAPIError as e:
            logger.error(f"Final batch export failed: {e}")
            failed += len(highlights_batch)

    # Update sync timestamp
    sync = _get_or_create_sync(user)
    sync.mark_export()

    return {"exported": exported, "failed": failed}


@app.task(queue=CONNECTORS)
def import_readwise_highlights(user_id: int) -> dict:
    """
    Import highlights from Readwise for a user.

    Args:
        user_id: ID of the User

    Returns:
        Dict with import statistics
    """
    try:
        user = models.User.objects.get(id=user_id)
    except models.User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {"error": "User not found"}

    if not user.readwise_token:
        return {"error": "No Readwise token configured"}

    sync = _get_or_create_sync(user)
    client = ReadwiseClient(user.readwise_token)

    # Get highlights updated since last import
    updated_after = sync.last_import_at

    try:
        books = client.export_highlights(updated_after=updated_after)
    except ReadwiseAPIError as e:
        logger.error(f"Failed to fetch Readwise highlights: {e}")
        return {"error": str(e)}

    imported = 0
    skipped = 0
    no_match = 0

    for book_data in books:
        book_title = book_data.get("title", "")
        book_author = book_data.get("author", "")
        readwise_book_id = book_data.get("user_book_id")

        # Try to match the book in BookWyrm
        matched_edition = _match_book(book_title, book_author)

        for highlight in book_data.get("highlights", []):
            readwise_id = highlight.get("id")
            if not readwise_id:
                continue

            # Check if already imported
            existing = models.ReadwiseSyncedHighlight.objects.filter(
                user=user, readwise_id=readwise_id
            ).first()

            if existing:
                skipped += 1
                continue

            highlight_text = highlight.get("text", "").strip()
            if not highlight_text:
                skipped += 1
                continue

            # Create tracking record
            synced_highlight = models.ReadwiseSyncedHighlight.objects.create(
                user=user,
                readwise_id=readwise_id,
                readwise_book_id=readwise_book_id,
                book_title=book_title,
                book_author=book_author,
                highlight_text=highlight_text[:1000],  # Truncate for storage
                matched_book=matched_edition,
            )

            if not matched_edition:
                no_match += 1
                logger.info(
                    f"No book match for Readwise highlight {readwise_id}: "
                    f"'{book_title}' by {book_author}"
                )
                continue

            # Create quotation
            try:
                with transaction.atomic():
                    # Parse location
                    location = highlight.get("location")
                    location_type = highlight.get("location_type")
                    position = str(location) if location else None
                    position_mode = "PG" if location_type == "page" else None

                    # Parse timestamp
                    highlighted_at = highlight.get("highlighted_at")
                    if highlighted_at:
                        try:
                            published_date = datetime.fromisoformat(
                                highlighted_at.replace("Z", "+00:00")
                            )
                        except ValueError:
                            published_date = timezone.now()
                    else:
                        published_date = timezone.now()

                    quotation = models.Quotation.objects.create(
                        user=user,
                        book=matched_edition,
                        quote=highlight_text,
                        raw_quote=highlight_text,
                        content=highlight.get("note", "") or "",
                        position=position,
                        position_mode=position_mode,
                        privacy=user.default_post_privacy,
                        published_date=published_date,
                        readwise_highlight_id=readwise_id,
                    )

                    # Link quotation to tracking record
                    synced_highlight.quotation = quotation
                    synced_highlight.save(update_fields=["quotation"])

                    imported += 1
                    logger.info(
                        f"Imported Readwise highlight {readwise_id} as quotation {quotation.id}"
                    )

            except Exception as e:
                logger.error(f"Failed to create quotation from highlight {readwise_id}: {e}")

    # Update sync timestamp
    sync.mark_import()

    return {
        "imported": imported,
        "skipped": skipped,
        "no_match": no_match,
        "total_books": len(books),
    }
