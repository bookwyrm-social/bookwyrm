""" ActivityPub-specific json response wrapper """
from django.http import JsonResponse

from .base_activity import ActivityEncoder


class ActivitypubResponse(JsonResponse):
    """
    A class to be used in any place that's serializing responses for
    Activitypub enabled clients. Uses JsonResponse under the hood, but already
    configures some stuff beforehand. Made to be a drop-in replacement of
    JsonResponse.
    """

    def __init__(
        self,
        data,
        encoder=ActivityEncoder,
        safe=False,
        json_dumps_params=None,
        **kwargs
    ):

        if "content_type" not in kwargs:
            kwargs["content_type"] = "application/activity+json"

        super().__init__(data, encoder, safe, json_dumps_params, **kwargs)
