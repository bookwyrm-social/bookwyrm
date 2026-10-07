"""endpoints for getting updates about activity"""

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse, HttpRequest
from django.utils.translation import ngettext

from bookwyrm import activitystreams


@login_required
def get_notification_count(request: HttpRequest):
    """any notifications waiting?"""
    return JsonResponse(
        {
            "count": request.user.unread_notification_count,
            "has_mentions": request.user.has_unread_mentions,
        }
    )


@login_required
def get_unread_status_string(request: HttpRequest, stream: str = "home"):
    """any unread statuses for this feed?"""
    activity_stream = activitystreams.streams.get(stream)
    if not activity_stream:
        raise Http404

    counts_by_type = activity_stream.get_unread_count_by_status_type(
        request.user
    ).items()
    if counts_by_type == {}:
        count = activity_stream.get_unread_count(request.user)
    else:
        # only consider the types that are visible in the feed
        allowed_status_types = request.user.feed_status_types
        count = sum(c for (k, c) in counts_by_type if k in allowed_status_types)
        # if "everything else" is allowed, add other types to the sum
        count += sum(
            c
            for (k, c) in counts_by_type
            if k not in ["review", "comment", "quotation"]
        )

    if not count:
        return JsonResponse({})

    translation_string = lambda c: ngettext(
        "Load %(count)d unread status", "Load %(count)d unread statuses", c
    ) % {"count": c}

    return JsonResponse({"count": translation_string(count)})
