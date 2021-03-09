""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required, permission_required
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
    """ list of reports  """

    def get(self, request):
        """ view current reports """
        resolved = request.GET.get("resolved", False)
        data = {
            "resolved": resolved,
            "reports": models.Report.objects.filter(resolved=resolved),
        }
        return TemplateResponse(request, "settings/reports.html", data)


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
    """ view a specific report """

    def get(self, request, report_id):
        """ load a report """
        data = {"report": get_object_or_404(models.Report, id=report_id)}
        return TemplateResponse(request, "settings/report.html", data)


@login_required
@require_POST
def make_report(request):
    """ a user reports something """
    form = forms.ReportForm(request.POST)
    if not form.is_valid():
        print(form.errors)
        return redirect(request.headers.get("Referer", "/"))

    form.save()
    return redirect(request.headers.get("Referer", "/"))
