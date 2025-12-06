"""Daily newsletter generation and sending"""
import logging
import zoneinfo
from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Q

from bookwyrm import models
from bookwyrm.emailing import email_data, format_email, send_email
from bookwyrm.tasks import app, EMAIL


logger = logging.getLogger(__name__)


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


def send_newsletter_to_user(user, activities, date_str):
    """Send newsletter email to a single user"""
    data = email_data()
    data["user"] = user.display_name
    data["date_str"] = date_str

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

    # Own activities (flat list - no grouping needed since it's all from one user)
    data["own_activities"] = {
        "reviews": own_reviews[:3],  # Limit to 3
        "comments": own_comments[:3],
        "quotations": own_quotations[:3],
        "shelf_changes": own_shelf_changes[:3],
    }

    # Followed activities grouped by user (max 3 items per user)
    data["followed_activities"] = {
        "reviews": group_activities_by_user(followed_reviews, max_per_user=3),
        "comments": group_activities_by_user(followed_comments, max_per_user=3),
        "quotations": group_activities_by_user(followed_quotations, max_per_user=3),
        "shelf_changes": group_activities_by_user(followed_shelf_changes, max_per_user=3),
    }

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


@app.task(queue=EMAIL)
def send_daily_newsletter():
    """
    Celery task to send daily newsletter to subscribed users.

    Scheduled to run HOURLY via celery beat. Only sends to users
    where it's currently 6 AM in their timezone, ensuring everyone
    gets their newsletter at a consistent local time.
    """
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

            send_newsletter_to_user(user, activities, date_str)
            sent_count += 1

        except Exception as e:  # pylint: disable=broad-except
            # Log error but continue with other users
            logger.error("Failed to send newsletter to user %s: %s", user.id, e)

    logger.info(
        "Daily newsletter: sent %d, skipped %d (no activity), %d (wrong timezone hour)",
        sent_count,
        skip_count,
        timezone_skip_count,
    )
