"""Daily newsletter generation and sending"""
import logging
import zoneinfo
from datetime import datetime, timedelta

from django.db.models import Q

from bookwyrm import models
from bookwyrm.emailing import email_data, format_email, send_email
from bookwyrm.tasks import app, EMAIL


logger = logging.getLogger(__name__)


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

    # Group activities by user for better presentation
    data["own_activities"] = {
        "reviews": [a for a in activities["reviews"] if a.user_id == user.id],
        "comments": [a for a in activities["comments"] if a.user_id == user.id],
        "quotations": [a for a in activities["quotations"] if a.user_id == user.id],
        "shelf_changes": [
            a for a in activities["shelf_changes"] if a.user_id == user.id
        ],
        "reading_progress": [
            a for a in activities["reading_progress"] if a.user_id == user.id
        ],
    }
    data["followed_activities"] = {
        "reviews": [a for a in activities["reviews"] if a.user_id != user.id],
        "comments": [a for a in activities["comments"] if a.user_id != user.id],
        "quotations": [a for a in activities["quotations"] if a.user_id != user.id],
        "shelf_changes": [
            a for a in activities["shelf_changes"] if a.user_id != user.id
        ],
        "reading_progress": [
            a for a in activities["reading_progress"] if a.user_id != user.id
        ],
    }

    send_email.delay(user.email, *format_email("daily_newsletter", data))


@app.task(queue=EMAIL)
def send_daily_newsletter():
    """
    Celery task to send daily newsletter to subscribed users.
    Scheduled to run at 8 AM UTC via celery beat.
    """
    # Get all active, local users who have subscribed
    subscribed_users = models.User.objects.filter(
        is_active=True,
        local=True,
        newsletter_subscription=True,
    ).exclude(Q(email__isnull=True) | Q(email=""))

    sent_count = 0
    skip_count = 0

    for user in subscribed_users:
        try:
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
        "Daily newsletter: sent %d, skipped %d (no activity)", sent_count, skip_count
    )
