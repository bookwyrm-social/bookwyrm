""" manage user """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_users", raise_exception=True),
    name="dispatch",
)
class UserAdmin(View):
    """ admin view of users on this server """

    def get(self, request):
        """ list of users """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        filters = {}
        server = request.GET.get("server")
        if server:
            server = models.FederatedServer.objects.filter(server_name=server).first()
            filters["federated_server"] = server
            filters["federated_server__isnull"] = False
        username = request.GET.get("username")
        if username:
            filters["username__icontains"] = username

        users = models.User.objects.filter(**filters)

        sort = request.GET.get("sort", "-created_date")
        sort_fields = [
            "created_date",
            "last_active_date",
            "username",
            "federated_server__server_name",
            "is_active",
        ]
        if sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            users = users.order_by(sort)

        paginated = Paginator(users, PAGE_LENGTH)
        data = {
            "users": paginated.get_page(page),
            "sort": sort,
            "server": server,
        }
        return TemplateResponse(request, "settings/user_admin.html", data)
