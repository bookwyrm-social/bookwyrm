"""custom 403 handler to enable context processors"""
from django.template.response import TemplateResponse


def permission_denied(request, exception):  # pylint: disable=unused-argument
    """permission denied page"""

    return TemplateResponse(request, "403.html")
