""" endpoints for getting updates about activity """
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from bookwyrm import activitystreams


@login_required
def get_notification_count(request):
    """any notifications waiting?"""
    return JsonResponse(
        {
            "count": request.user.unread_notification_count,
            "has_mentions": request.user.has_unread_mentions,
        }
    )


@login_required
def get_unread_status_count(request, stream="home"):
    """any unread statuses for this feed?"""
    stream = activitystreams.streams.get(stream)
    if not stream:
        return JsonResponse({})
    return JsonResponse({"count": stream.get_unread_count(request.user)})
