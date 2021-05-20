""" make announcements """
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class Announcements(View):
    """tell everyone"""

    def get(self, request):
        """view and create announcements"""
        data = {
            "announcements": models.Announcement.objects.all(),
            "form": forms.AnnouncementForm(),
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
            "announcements": models.Announcement.objects.all(),
            "form": form,
        }
        return TemplateResponse(request, "settings/announcements.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class Announcement(View):
    """delete or edit an announcement"""

    def get(self, request, announcement_id):
        """view announcement"""
        announcement = get_object_or_404(models.Announcement, id=announcement_id)
        data = {
            "announcement": announcement,
            "form": forms.AnnouncementForm(instance=announcement),
        }
        return TemplateResponse(request, "settings/announcement.html", data)

    def post(self, request, announcement_id):
        """edit the site settings"""
        announcement = get_object_or_404(models.Announcement, id=announcement_id)
        form = forms.AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            form.save()
        data = {
            "announcements": models.Announcement.objects.all(),
            "form": form,
        }
        return TemplateResponse(request, "settings/announcement.html", data)
