"""custom 500 handler to enable context processors"""
from django.template.response import TemplateResponse


def server_error(request):
    """server error page"""

    return TemplateResponse(request, "500.html")
