""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.views.helpers import redirect_to_referer
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
@method_decorator(
    permission_required("bookwyrm.moderate_post", raise_exception=True),
    name="dispatch",
)
class ReportsAdmin(View):
    """list of reports"""

    def get(self, request):
        """view current reports"""
        filters = {}

        # we sometimes want to see all reports, regardless of resolution
        if request.GET.get("resolved") == "all":
            resolved = "all"
        else:
            resolved = request.GET.get("resolved") == "true"

        server = request.GET.get("server")
        if server:
            filters["user__federated_server__server_name"] = server
        username = request.GET.get("username")
        if username:
            filters["user__username__icontains"] = username
        if resolved != "all":
            filters["resolved"] = resolved

        reports = models.Report.objects.filter(**filters)
        paginated = Paginator(reports, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "resolved": resolved,
            "server": server,
            "reports": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
        }
        return TemplateResponse(request, "settings/reports/reports.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
@method_decorator(
    permission_required("bookwyrm.moderate_post", raise_exception=True),
    name="dispatch",
)
class ReportAdmin(View):
    """view a specific report"""

    def get(self, request, report_id):
        """load a report"""
        data = {
            "report": get_object_or_404(models.Report, id=report_id),
            "group_form": forms.UserGroupForm(),
        }
        return TemplateResponse(request, "settings/reports/report.html", data)

    def post(self, request, report_id):
        """comment on a report"""
        report = get_object_or_404(models.Report, id=report_id)
        models.ReportComment.objects.create(
            user=request.user,
            report=report,
            note=request.POST.get("note"),
        )
        return redirect("settings-report", report.id)


@login_required
@permission_required("bookwyrm.moderate_user")
def suspend_user(request, user_id):
    """mark an account as inactive"""
    user = get_object_or_404(models.User, id=user_id)
    user.is_active = False
    user.deactivation_reason = "moderator_suspension"
    # this isn't a full deletion, so we don't want to tell the world
    user.save(broadcast=False)
    return redirect_to_referer(request, "settings-user", user.id)


@login_required
@permission_required("bookwyrm.moderate_user")
def unsuspend_user(request, user_id):
    """mark an account as inactive"""
    user = get_object_or_404(models.User, id=user_id)
    user.is_active = True
    user.deactivation_reason = None
    # this isn't a full deletion, so we don't want to tell the world
    user.save(broadcast=False)
    return redirect_to_referer(request, "settings-user", user.id)


@login_required
@permission_required("bookwyrm.moderate_user")
def moderator_delete_user(request, user_id):
    """permanently delete a user"""
    user = get_object_or_404(models.User, id=user_id)

    # we can't delete users on other instances
    if not user.local:
        raise PermissionDenied()

    form = forms.DeleteUserForm(request.POST, instance=user)

    moderator = models.User.objects.get(id=request.user.id)
    # check the moderator's password
    if form.is_valid() and moderator.check_password(form.cleaned_data["password"]):
        user.deactivation_reason = "moderator_deletion"
        user.delete()
        return redirect_to_referer(request, "settings-user", user.id)

    form.errors["password"] = ["Invalid password"]

    data = {"user": user, "group_form": forms.UserGroupForm(), "form": form}
    return TemplateResponse(request, "settings/users/user.html", data)


@login_required
@permission_required("bookwyrm.moderate_post")
def resolve_report(_, report_id):
    """mark a report as (un)resolved"""
    report = get_object_or_404(models.Report, id=report_id)
    report.resolved = not report.resolved
    report.save()
    if not report.resolved:
        return redirect("settings-report", report.id)
    return redirect("settings-reports")
