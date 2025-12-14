"""Daily newsletter generation and sending"""
import base64
import logging
import mimetypes
import zoneinfo
from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO

import requests
from django.db.models import Q

from celery import shared_task

from bookwyrm import models
from bookwyrm.emailing import email_data, format_email, send_email
from bookwyrm.tasks import EMAIL


logger = logging.getLogger(__name__)

# HTTP session for downloading images
_http_session = None


def get_http_session():
    """Get or create HTTP session for image downloads"""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        _http_session.headers.update({"User-Agent": "BookWyrm Newsletter"})
    return _http_session


def image_to_base64(image_url, max_size_kb=100):
    """
    Download image from URL and convert to base64 data URI.
    Returns None if download fails or image is too large.
    """
    if not image_url:
        return None

    try:
        session = get_http_session()
        response = session.get(image_url, timeout=5)
        response.raise_for_status()

        # Check size (limit to max_size_kb to keep email size reasonable)
        if len(response.content) > max_size_kb * 1024:
            logger.debug("Image too large for embedding: %s", image_url)
            return None

        # Determine mime type
        content_type = response.headers.get("content-type", "image/jpeg")
        if ";" in content_type:
            content_type = content_type.split(";")[0].strip()

        # Convert to base64
        b64_data = base64.b64encode(response.content).decode("utf-8")
        return f"data:{content_type};base64,{b64_data}"

    except Exception as e:
        logger.debug("Failed to download image %s: %s", image_url, e)
        return None


def get_book_cover_base64(book, base_url):
    """Get base64 encoded book cover or None"""
    if not book or not book.cover:
        return None
    cover_url = book.cover.url
    # Only prepend base_url if not already absolute
    if not cover_url.startswith(("http://", "https://")):
        cover_url = f"{base_url}{cover_url}"
    return image_to_base64(cover_url, max_size_kb=50)


def get_user_avatar_base64(user, base_url):
    """Get base64 encoded user avatar or None"""
    if not user or not user.avatar:
        return None
    avatar_url = user.avatar.url
    # Only prepend base_url if not already absolute
    if not avatar_url.startswith(("http://", "https://")):
        avatar_url = f"{base_url}{avatar_url}"
    return image_to_base64(avatar_url, max_size_kb=30)


def truncate_description(text, max_length=150):
    """Truncate text to max_length with ellipsis, breaking at word boundary"""
    if not text or len(text) <= max_length:
        return text or ""
    truncated = text[:max_length]
    # Try to break at last space to avoid cutting words
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "..."


def dedupe_reviews_by_book(reviews):
    """
    Deduplicate reviews for the same book by the same user.

    When a user rates and reviews a book, it may create two statuses:
    - ReviewRating (rating only)
    - Review (rating + content)

    This function keeps only the Review with content when both exist,
    preventing duplicate entries in the newsletter.

    Returns deduplicated list of reviews.
    """
    # Group by (user_id, book_id)
    by_user_book = defaultdict(list)
    for review in reviews:
        book_id = getattr(review.book, "id", None) if review.book else None
        key = (review.user_id, book_id)
        by_user_book[key].append(review)

    result = []
    for (user_id, book_id), user_reviews in by_user_book.items():
        if len(user_reviews) == 1:
            result.append(user_reviews[0])
        else:
            # Multiple reviews for same book by same user
            # Prefer reviews with content over rating-only
            with_content = [r for r in user_reviews if r.content]
            if with_content:
                # Take the most recent one with content
                result.append(max(with_content, key=lambda r: r.published_date))
            else:
                # All are rating-only, take most recent
                result.append(max(user_reviews, key=lambda r: r.published_date))

    # Sort by published_date descending to maintain original order
    result.sort(key=lambda r: r.published_date, reverse=True)
    return result


def group_activities_by_user(activities, max_per_user=3):
    """
    Group activities by user, limiting to max_per_user items each.

    Returns list of dicts: [{'user': User, 'items': [activity1, activity2, ...]}]
    """
    grouped = defaultdict(list)
    for activity in activities:
        if len(grouped[activity.user_id]) < max_per_user:
            grouped[activity.user_id].append(activity)

    # Convert to list of dicts with user object
    result = []
    for user_id, items in grouped.items():
        if items:
            result.append({"user": items[0].user, "items": items})
    return result


def get_yesterday_range_for_user(user):
    """
    Get yesterday's date range in user's preferred timezone.

    Returns (start_datetime, end_datetime) as timezone-aware UTC datetimes.
    """
    try:
        user_tz = zoneinfo.ZoneInfo(user.preferred_timezone)
    except (ValueError, KeyError):
        user_tz = zoneinfo.ZoneInfo("UTC")

    # Current time in user's timezone
    now_user_tz = datetime.now(user_tz)

    # Yesterday in user's timezone
    yesterday = now_user_tz.date() - timedelta(days=1)

    # Start and end of yesterday in user's timezone
    start_of_yesterday = datetime.combine(
        yesterday, datetime.min.time(), tzinfo=user_tz
    )
    end_of_yesterday = datetime.combine(
        yesterday, datetime.max.time(), tzinfo=user_tz
    )

    # Convert to UTC for database queries
    utc = zoneinfo.ZoneInfo("UTC")
    return (
        start_of_yesterday.astimezone(utc),
        end_of_yesterday.astimezone(utc),
    )


def get_newsletter_activities(user, start_date, end_date):
    """
    Query activities for user + followed users within date range.

    Returns dict with keys: reviews, comments, quotations, shelf_changes, reading_progress
    """
    # Get user IDs: self + following
    following_ids = list(user.following.values_list("id", flat=True))
    user_ids = [user.id] + following_ids

    activities = {
        "reviews": [],
        "comments": [],
        "quotations": [],
        "shelf_changes": [],
        "reading_progress": [],
    }

    # Query Status subclasses (Review, Comment, Quotation)
    statuses = (
        models.Status.objects.select_subclasses()
        .filter(
            user_id__in=user_ids,
            published_date__gte=start_date,
            published_date__lt=end_date,
            deleted=False,
            privacy__in=["public", "unlisted", "followers"],
        )
        .select_related("user")
        .order_by("-published_date")
    )

    for status in statuses:
        if isinstance(status, models.Review):
            activities["reviews"].append(status)
        elif isinstance(status, models.Comment):
            activities["comments"].append(status)
        elif isinstance(status, models.Quotation):
            activities["quotations"].append(status)

    # Dedupe reviews: when user rates AND reviews same book, show only the review
    activities["reviews"] = dedupe_reviews_by_book(activities["reviews"])

    # Query ShelfBook changes (shelf moves)
    shelf_changes = (
        models.ShelfBook.objects.filter(
            user_id__in=user_ids,
            shelved_date__gte=start_date,
            shelved_date__lt=end_date,
        )
        .select_related("user", "book", "shelf")
        .order_by("-shelved_date")
    )
    activities["shelf_changes"] = list(shelf_changes)

    # Query ReadThrough progress updates
    progress_updates = (
        models.ReadThrough.objects.filter(
            user_id__in=user_ids,
            updated_date__gte=start_date,
            updated_date__lt=end_date,
        )
        .select_related("user", "book")
        .order_by("-updated_date")
    )
    activities["reading_progress"] = list(progress_updates)

    return activities


def has_activities(activities):
    """Check if there are any activities to report"""
    return any(len(activities[key]) > 0 for key in activities)


def prepare_activity_with_images(activity, base_url, activity_type="status"):
    """
    Prepare an activity dict with embedded base64 images.
    Returns dict with activity data and image data URIs.
    """
    result = {
        "activity": activity,
        "book_cover": None,
        "user_avatar": None,
    }

    # Get book cover
    book = getattr(activity, "book", None)
    if book:
        result["book_cover"] = get_book_cover_base64(book, base_url)

    # Get user avatar for followed activities
    if activity_type == "followed":
        result["user_avatar"] = get_user_avatar_base64(activity.user, base_url)

    return result


def prepare_grouped_activities_with_images(grouped, base_url):
    """
    Prepare grouped activities with embedded images.
    Returns list of groups with user avatars and item book covers.
    """
    result = []
    for group in grouped:
        group_data = {
            "user": group["user"],
            "user_avatar": get_user_avatar_base64(group["user"], base_url),
            "items": [],
        }
        for item in group["items"]:
            group_data["items"].append({
                "activity": item,
                "book_cover": get_book_cover_base64(getattr(item, "book", None), base_url),
            })
        result.append(group_data)
    return result


def get_currently_reading(user):
    """
    Get books the user is currently reading.
    Returns list of ReadThrough objects with active reading.
    """
    return list(
        models.ReadThrough.objects.filter(
            user=user,
            start_date__isnull=False,
            finish_date__isnull=True,
        )
        .select_related("book")
        .order_by("-start_date")[:5]
    )


def send_newsletter_to_user(user, activities, date_str, start_date):
    """Send newsletter email to a single user"""
    data = email_data()
    data["user"] = user.display_name
    data["date_str"] = date_str
    base_url = data.get("base_url", "")

    # Date components for editorial header
    data["date_day"] = start_date.day
    data["date_month"] = start_date.strftime("%B")
    data["date_year"] = start_date.year

    # URLs for footer
    data["feed_url"] = base_url
    data["email_preferences_url"] = f"{base_url}/preferences/profile"

    # Split into own vs followed activities
    own_reviews = [a for a in activities["reviews"] if a.user_id == user.id]
    own_comments = [a for a in activities["comments"] if a.user_id == user.id]
    own_quotations = [a for a in activities["quotations"] if a.user_id == user.id]
    own_shelf_changes = [a for a in activities["shelf_changes"] if a.user_id == user.id]

    followed_reviews = [a for a in activities["reviews"] if a.user_id != user.id]
    followed_comments = [a for a in activities["comments"] if a.user_id != user.id]
    followed_quotations = [a for a in activities["quotations"] if a.user_id != user.id]
    followed_shelf_changes = [
        a for a in activities["shelf_changes"] if a.user_id != user.id
    ]

    # Own activities with embedded images (flat list)
    data["own_activities"] = {
        "reviews": [
            prepare_activity_with_images(a, base_url) for a in own_reviews[:5]
        ],
        "comments": [
            prepare_activity_with_images(a, base_url) for a in own_comments[:3]
        ],
        "quotations": [
            prepare_activity_with_images(a, base_url) for a in own_quotations[:3]
        ],
        "shelf_changes": [
            prepare_activity_with_images(a, base_url) for a in own_shelf_changes[:3]
        ],
    }

    # Featured review (first review with content) and grid reviews
    all_reviews_prepared = [
        prepare_activity_with_images(a, base_url, "followed")
        for a in activities["reviews"][:6]
    ]
    data["featured_review"] = all_reviews_prepared[0] if all_reviews_prepared else None
    data["grid_reviews"] = all_reviews_prepared[1:5] if len(all_reviews_prepared) > 1 else []

    # Featured highlight (first quotation)
    all_quotations = activities["quotations"][:3]
    data["featured_highlight"] = (
        prepare_activity_with_images(all_quotations[0], base_url, "followed")
        if all_quotations else None
    )

    # Followed activities grouped by user with embedded images
    data["followed_activities"] = {
        "reviews": prepare_grouped_activities_with_images(
            group_activities_by_user(followed_reviews, max_per_user=3), base_url
        ),
        "comments": prepare_grouped_activities_with_images(
            group_activities_by_user(followed_comments, max_per_user=3), base_url
        ),
        "quotations": prepare_grouped_activities_with_images(
            group_activities_by_user(followed_quotations, max_per_user=3), base_url
        ),
        "shelf_changes": prepare_grouped_activities_with_images(
            group_activities_by_user(followed_shelf_changes, max_per_user=3), base_url
        ),
    }

    # Currently reading books with covers
    currently_reading = get_currently_reading(user)
    data["currently_reading"] = [
        {
            "readthrough": rt,
            "book_cover": get_book_cover_base64(rt.book, base_url),
        }
        for rt in currently_reading
    ]

    send_email.delay(user.email, *format_email("daily_newsletter", data))


def is_target_hour_for_user(user, target_hour=6):
    """
    Check if it's currently the target hour (default 6 AM) in user's timezone.
    Used for sending newsletters at a consistent local time for each user.
    """
    try:
        user_tz = zoneinfo.ZoneInfo(user.preferred_timezone)
    except (ValueError, KeyError):
        user_tz = zoneinfo.ZoneInfo("UTC")

    now_user_tz = datetime.now(user_tz)
    return now_user_tz.hour == target_hour


@shared_task(queue=EMAIL)
def send_daily_newsletter():
    """
    Celery task to send daily newsletter to subscribed users.

    Scheduled to run HOURLY via celery beat.
    DEBUG MODE: Sends to all users every hour (timezone check disabled).
    PRODUCTION: Set NEWSLETTER_DEBUG=false to enable 6 AM timezone check.
    """
    import os
    debug_mode = os.environ.get("NEWSLETTER_DEBUG", "true").lower() == "true"

    # Get all active, local users who have subscribed
    subscribed_users = models.User.objects.filter(
        is_active=True,
        local=True,
        newsletter_subscription=True,
    ).exclude(Q(email__isnull=True) | Q(email=""))

    sent_count = 0
    skip_count = 0
    timezone_skip_count = 0

    for user in subscribed_users:
        try:
            # In debug mode, skip timezone check and send every hour
            if not debug_mode:
                # Only send to users where it's currently 6 AM in their timezone
                if not is_target_hour_for_user(user, target_hour=6):
                    timezone_skip_count += 1
                    continue

            start_date, end_date = get_yesterday_range_for_user(user)
            activities = get_newsletter_activities(user, start_date, end_date)

            # Skip users with no activities
            if not has_activities(activities):
                skip_count += 1
                continue

            # Format date string
            date_str = start_date.strftime("%B %d, %Y")

            send_newsletter_to_user(user, activities, date_str, start_date)
            sent_count += 1

        except Exception as e:  # pylint: disable=broad-except
            # Log error but continue with other users
            logger.error("Failed to send newsletter to user %s: %s", user.id, e)

    logger.info(
        "Daily newsletter (debug=%s): sent %d, skipped %d (no activity), %d (wrong timezone hour)",
        debug_mode,
        sent_count,
        skip_count,
        timezone_skip_count,
    )
