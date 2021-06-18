""" make announcements """
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
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class Announcements(View):
    """tell everyone"""

    def get(self, request):
        """view and create announcements"""
        announcements = models.Announcement.objects

        sort = request.GET.get("sort", "-created_date")
        sort_fields = [
            "created_date",
            "preview",
            "start_date",
            "end_date",
            "active",
        ]
        if sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            announcements = announcements.order_by(sort)
        data = {
            "announcements": Paginator(announcements, PAGE_LENGTH).get_page(
                request.GET.get("page")
            ),
            "form": forms.AnnouncementForm(),
            "sort": sort,
        }
        return TemplateResponse(request, "settings/announcements.html", data)

    def post(self, request):
        """edit the site settings"""
        form = forms.AnnouncementForm(request.POST)
        if form.is_valid():
            form.save()
            # reset the create form
            form = forms.AnnouncementForm()
        data = {
            "announcements": Paginator(
                models.Announcement.objects.all(), PAGE_LENGTH
            ).get_page(request.GET.get("page")),
            "form": form,
        }
        return TemplateResponse(request, "settings/announcements.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class Announcement(View):
    """edit an announcement"""

    def get(self, request, announcement_id):
        """view announcement"""
        announcement = get_object_or_404(models.Announcement, id=announcement_id)
        data = {
            "announcement": announcement,
            "form": forms.AnnouncementForm(instance=announcement),
        }
        return TemplateResponse(request, "settings/announcement.html", data)

    def post(self, request, announcement_id):
        """edit announcement"""
        announcement = get_object_or_404(models.Announcement, id=announcement_id)
        form = forms.AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            announcement = form.save()
            form = forms.AnnouncementForm(instance=announcement)
        data = {
            "announcement": announcement,
            "form": form,
        }
        return TemplateResponse(request, "settings/announcement.html", data)


@login_required
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def delete_announcement(_, announcement_id):
    """delete announcement"""
    announcement = get_object_or_404(models.Announcement, id=announcement_id)
    announcement.delete()
    return redirect("settings-announcements")
