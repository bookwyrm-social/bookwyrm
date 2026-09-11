"""Block IP addresses"""

from django.http import Http404
from bookwyrm import models
from bookwyrm.utils.ip_utils import client_ip_address


class IPBlocklistMiddleware:
    """check incoming traffic against an IP block-list"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        address = client_ip_address(request)
        if models.IPBlocklist.objects.filter(address=address).exists():
            raise Http404()
        return self.get_response(request)
