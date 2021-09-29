""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models


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
class Reports(View):
    """list of reports"""

    def get(self, request):
        """view current reports"""
        filters = {}

        resolved = request.GET.get("resolved") == "true"
        server = request.GET.get("server")
        if server:
            filters["user__federated_server__server_name"] = server
        username = request.GET.get("username")
        if username:
            filters["user__username__icontains"] = username
        filters["resolved"] = resolved
        data = {
            "resolved": resolved,
            "server": server,
            "reports": models.Report.objects.filter(**filters),
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
class Report(View):
    """view a specific report"""

    def get(self, request, report_id):
        """load a report"""
        data = {
            "report": get_object_or_404(models.Report, id=report_id),
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
@permission_required("bookwyrm_moderate_user")
def suspend_user(_, user_id):
    """mark an account as inactive"""
    user = get_object_or_404(models.User, id=user_id)
    user.is_active = False
    user.deactivation_reason = "moderator_suspension"
    # this isn't a full deletion, so we don't want to tell the world
    user.save(broadcast=False)
    return redirect("settings-user", user.id)


@login_required
@permission_required("bookwyrm_moderate_user")
def unsuspend_user(_, user_id):
    """mark an account as inactive"""
    user = get_object_or_404(models.User, id=user_id)
    user.is_active = True
    user.deactivation_reason = None
    # this isn't a full deletion, so we don't want to tell the world
    user.save(broadcast=False)
    return redirect("settings-user", user.id)


@login_required
@permission_required("bookwyrm_moderate_user")
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
        return redirect("settings-user", user.id)

    form.errors["password"] = ["Invalid password"]

    data = {"user": user, "group_form": forms.UserGroupForm(), "form": form}
    return TemplateResponse(request, "user_admin/user.html", data)


@login_required
@permission_required("bookwyrm_moderate_post")
def resolve_report(_, report_id):
    """mark a report as (un)resolved"""
    report = get_object_or_404(models.Report, id=report_id)
    report.resolved = not report.resolved
    report.save()
    if not report.resolved:
        return redirect("settings-report", report.id)
    return redirect("settings-reports")


@login_required
@require_POST
def make_report(request):
    """a user reports something"""
    form = forms.ReportForm(request.POST)
    if not form.is_valid():
        raise ValueError(form.errors)

    form.save()
    return redirect(request.headers.get("Referer", "/"))
