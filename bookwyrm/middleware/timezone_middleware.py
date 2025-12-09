"""Makes the app aware of the users timezone"""

import zoneinfo

from django.utils import timezone


class TimezoneMiddleware:
    """Determine the timezone based on the request"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            timezone.activate(zoneinfo.ZoneInfo(request.user.preferred_timezone))
        else:
            timezone.deactivate()
        return self.get_response(request)
