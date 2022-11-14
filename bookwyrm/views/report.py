""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import emailing, forms, models


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class Report(View):
    """Make reports"""

    def get(self, request, user_id=None, status_id=None, link_id=None):
        """static view of report modal"""
        data = {"user": None}
        if user_id:
            # but normally we should have an error if the user is not found
            data["user"] = get_object_or_404(models.User, id=user_id)

        if status_id:
            data["status"] = status_id
        if link_id:
            data["link"] = get_object_or_404(models.Link, id=link_id)

        return TemplateResponse(request, "report.html", data)

    def post(self, request):
        """a user reports something"""
        form = forms.ReportForm(request.POST)
        if not form.is_valid():
            raise ValueError(form.errors)

        report = form.save(request)
        if report.links.exists():
            # revert the domain to pending
            domain = report.links.first().domain
            domain.status = "pending"
            domain.save()
        emailing.moderation_report_email(report)
        return redirect("/")
