""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.models.report import USER_SUSPENSION, USER_UNSUSPENSION, USER_DELETION
from bookwyrm.views.helpers import redirect_to_referer, is_api_request
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
        report = get_object_or_404(models.Report, id=report_id)
        if is_api_request(request):
            return ActivitypubResponse(report.to_activity(**request.GET))

        data = {
            "report": report,
            "group_form": forms.UserGroupForm(),
        }
        return TemplateResponse(request, "settings/reports/report.html", data)

    def post(self, request, report_id):
        """comment on a report"""
        report = get_object_or_404(models.Report, id=report_id)
        note = request.POST.get("note")
        report.comment(request.user, note)
        return redirect("settings-report", report.id)


@login_required
@permission_required("bookwyrm.moderate_user")
def suspend_user(request, user_id, report_id=None):
    """mark an account as inactive"""
    user = get_object_or_404(models.User, id=user_id)
    user.is_active = False
    user.deactivation_reason = "moderator_suspension"
    # this isn't a full deletion, so we don't want to tell the world
    user.save(broadcast=False)

    models.Report.record_action(report_id, USER_SUSPENSION, request.user)
    return redirect_to_referer(request, "settings-user", user.id)


@login_required
@permission_required("bookwyrm.moderate_user")
def unsuspend_user(request, user_id, report_id=None):
    """mark an account as inactive"""
    user = get_object_or_404(models.User, id=user_id)
    user.is_active = True
    user.deactivation_reason = None
    # this isn't a full deletion, so we don't want to tell the world
    user.save(broadcast=False)

    models.Report.record_action(report_id, USER_UNSUSPENSION, request.user)
    return redirect_to_referer(request, "settings-user", user.id)


@login_required
@permission_required("bookwyrm.moderate_user")
def moderator_delete_user(request, user_id, report_id=None):
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

        # make a note of the fact that we did this
        models.Report.record_action(report_id, USER_DELETION, request.user)
        return redirect_to_referer(request, "settings-user", user.id)

    form.errors["password"] = ["Invalid password"]

    data = {"user": user, "group_form": forms.UserGroupForm(), "form": form}
    return TemplateResponse(request, "settings/users/user.html", data)


@login_required
@permission_required("bookwyrm.moderate_post")
def resolve_report(request, report_id):
    """mark a report as (un)resolved"""
    report = get_object_or_404(models.Report, id=report_id)
    if report.resolved:
        report.reopen(request.user)
        return redirect("settings-report", report.id)

    report.resolve(request.user)
    return redirect("settings-reports")
