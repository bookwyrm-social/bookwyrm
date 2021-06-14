""" manage federated servers """
import json
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.control_federation", raise_exception=True),
    name="dispatch",
)
class Federation(View):
    """what servers do we federate with"""

    def get(self, request):
        """list of servers"""
        servers = models.FederatedServer.objects

        sort = request.GET.get("sort")
        sort_fields = ["created_date", "application_type", "server_name"]
        if not sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            sort = "created_date"
        servers = servers.order_by(sort)

        paginated = Paginator(servers, PAGE_LENGTH)

        data = {
            "servers": paginated.get_page(request.GET.get("page")),
            "sort": sort,
            "form": forms.ServerForm(),
        }
        return TemplateResponse(request, "settings/federation.html", data)


class AddFederatedServer(View):
    """manually add a server"""

    def get(self, request):
        """add server form"""
        data = {"form": forms.ServerForm()}
        return TemplateResponse(request, "settings/edit_server.html", data)

    def post(self, request):
        """add a server from the admin panel"""
        form = forms.ServerForm(request.POST)
        if not form.is_valid():
            data = {"form": form}
            return TemplateResponse(request, "settings/edit_server.html", data)
        server = form.save()
        return redirect("settings-federated-server", server.id)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.control_federation", raise_exception=True),
    name="dispatch",
)
class ImportServerBlocklist(View):
    """manually add a server"""

    def get(self, request):
        """add server form"""
        return TemplateResponse(request, "settings/server_blocklist.html")

    def post(self, request):
        """add a server from the admin panel"""
        json_data = json.load(request.FILES["json_file"])
        failed = []
        success_count = 0
        for item in json_data:
            server_name = item.get("instance")
            if not server_name:
                failed.append(item)
                continue
            info_link = item.get("url")

            with transaction.atomic():
                server, _ = models.FederatedServer.objects.get_or_create(
                    server_name=server_name,
                )
                server.notes = info_link
                server.save()
                server.block()
            success_count += 1
        data = {"failed": failed, "succeeded": success_count}
        return TemplateResponse(request, "settings/server_blocklist.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.control_federation", raise_exception=True),
    name="dispatch",
)
class FederatedServer(View):
    """views for handling a specific federated server"""

    def get(self, request, server):
        """load a server"""
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

    def post(self, request, server):  # pylint: disable=unused-argument
        """update note"""
        server = get_object_or_404(models.FederatedServer, id=server)
        server.notes = request.POST.get("notes")
        server.save()
        return redirect("settings-federated-server", server.id)


@login_required
@require_POST
@permission_required("bookwyrm.control_federation", raise_exception=True)
# pylint: disable=unused-argument
def block_server(request, server):
    """block a server"""
    server = get_object_or_404(models.FederatedServer, id=server)
    server.block()
    return redirect("settings-federated-server", server.id)


@login_required
@require_POST
@permission_required("bookwyrm.control_federation", raise_exception=True)
# pylint: disable=unused-argument
def unblock_server(request, server):
    """unblock a server"""
    server = get_object_or_404(models.FederatedServer, id=server)
    server.unblock()
    return redirect("settings-federated-server", server.id)
