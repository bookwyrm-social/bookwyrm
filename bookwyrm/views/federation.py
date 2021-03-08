""" manage federated servers """
from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.control_federation", raise_exception=True),
    name="dispatch",
)
class Federation(View):
    """ what servers do we federate with """

    def get(self, request):
        """ edit form """
        servers = models.FederatedServer.objects.all()
        data = {"servers": servers}
        return TemplateResponse(request, "settings/federation.html", data)
