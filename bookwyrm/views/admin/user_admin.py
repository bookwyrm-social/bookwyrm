""" manage user """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class UserAdminList(View):
    """admin view of users on this server"""

    def get(self, request, status="local"):
        """list of users"""
        filters = {}
        exclusions = {}
        if server := request.GET.get("server"):
            server = models.FederatedServer.objects.filter(server_name=server).first()
            filters["federated_server"] = server
            filters["federated_server__isnull"] = False

        if username := request.GET.get("username"):
            filters["username__icontains"] = username

        if email := request.GET.get("email"):
            filters["email__endswith"] = email

        filters["local"] = status in ["local", "deleted"]
        if status == "deleted":
            filters["deactivation_reason__icontains"] = "deletion"
        else:
            exclusions["deactivation_reason__icontains"] = "deletion"

        users = models.User.objects.filter(**filters).exclude(**exclusions)

        sort = request.GET.get("sort", "-created_date")
        sort_fields = [
            "created_date",
            "last_active_date",
            "username",
            "federated_server__server_name",
            "is_active",
        ]
        # pylint: disable=consider-using-f-string
        if sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            users = users.order_by(sort)

        paginated = Paginator(users, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "users": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "sort": sort,
            "server": server,
            "status": status,
        }
        return TemplateResponse(request, "settings/users/user_admin.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class UserAdmin(View):
    """moderate an individual user"""

    def get(self, request, user):
        """user view"""
        user = get_object_or_404(models.User, id=user)
        data = {"user": user, "group_form": forms.UserGroupForm()}
        return TemplateResponse(request, "settings/users/user.html", data)

    def post(self, request, user):
        """update user group"""
        user = get_object_or_404(models.User, id=user)

        if request.POST.get("groups") == "":
            user.groups.set([])
            form = forms.UserGroupForm(instance=user)
        else:
            form = forms.UserGroupForm(request.POST, instance=user)
            if form.is_valid():
                form.save(request)
        data = {"user": user, "group_form": form}
        return TemplateResponse(request, "settings/users/user.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class ActivateUserAdmin(View):
    """activate a user manually"""

    # pylint: disable=unused-argument
    def post(self, request, user):
        """activate user"""
        user = get_object_or_404(models.User, id=user)
        user.reactivate()
        return redirect("settings-user", user.id)
