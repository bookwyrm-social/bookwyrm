"""Middleware to display a custom 413 error page"""

from django.http import HttpResponse
from django.shortcuts import render
from django.core.exceptions import RequestDataTooBig


class FileTooBig:
    """Middleware to display a custom page when a
    RequestDataTooBig exception is thrown"""

    def __init__(self, get_response):
        """boilerplate __init__ from Django docs"""

        self.get_response = get_response

    def __call__(self, request):
        """If RequestDataTooBig is thrown, render the 413 error page"""

        try:
            body = request.body  # pylint: disable=unused-variable

        except RequestDataTooBig:

            rendered = render(request, "413.html")
            response = HttpResponse(rendered)
            return response

        response = self.get_response(request)
        return response
