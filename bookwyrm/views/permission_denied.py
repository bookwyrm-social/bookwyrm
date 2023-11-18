"""custom 403 handler to enable context processors"""

from django.http import HttpResponse
from django.template.response import TemplateResponse

from .helpers import is_api_request


def permission_denied(request, exception):  # pylint: disable=unused-argument
    """permission denied page"""

    if request.method == "POST" or is_api_request(request):
        return HttpResponse(status=403)

    return TemplateResponse(request, "403.html")
