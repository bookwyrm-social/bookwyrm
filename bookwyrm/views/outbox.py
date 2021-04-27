""" the good stuff! the books! """
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from bookwyrm import activitypub, models
from .helpers import is_bookwyrm_request


# pylint: disable= no-self-use
class Outbox(View):
    """outbox"""

    def get(self, request, username):
        """outbox for the requested user"""
        user = get_object_or_404(models.User, localname=username)
        filter_type = request.GET.get("type")
        if filter_type not in models.status_models:
            filter_type = None

        return JsonResponse(
            user.to_outbox(
                **request.GET,
                filter_type=filter_type,
                pure=not is_bookwyrm_request(request)
            ),
            encoder=activitypub.ActivityEncoder,
        )
