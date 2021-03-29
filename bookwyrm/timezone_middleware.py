import pytz

from django.utils import timezone


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            timezone.activate(pytz.timezone(request.user.preferred_timezone))
        else:
            timezone.activate(pytz.utc)
        response = self.get_response(request)
        timezone.deactivate()
        return response
