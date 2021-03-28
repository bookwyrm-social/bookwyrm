""" manage federated servers """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.control_federation", raise_exception=True),
    name="dispatch",
)
class Federation(View):
    """ what servers do we federate with """

    def get(self, request):
        """ list of servers """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        servers = models.FederatedServer.objects.all()

        sort = request.GET.get("sort")
        sort_fields = ["created_date", "application_type", "server_name"]
        if sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            servers = servers.order_by(sort)

        paginated = Paginator(servers, PAGE_LENGTH)
        data = {"servers": paginated.page(page), "sort": sort}
        return TemplateResponse(request, "settings/federation.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.control_federation", raise_exception=True),
    name="dispatch",
)
class FederatedServer(View):
    """ views for handling a specific federated server """

    def get(self, request, server):
        """ load a server """
        server = get_object_or_404(models.FederatedServer, id=server)
        users = server.user_set
        data = {
            "server": server,
            "users": users,
            "reports": models.Report.objects.filter(user__in=users.all()),
            "followed_by_us": users.filter(followers__local=True),
            "followed_by_them": users.filter(following__local=True),
            "blocked_by_us": models.UserBlocks.objects.filter(
                user_subject__in=users.all()
            ),
        }
        return TemplateResponse(request, "settings/federated_server.html", data)
