""" make announcements """
from django.contrib.auth.decorators import login_required, permission_required
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
        data = {
            "announcements": models.Announcement.objects.all(),
            "form": forms.AnnouncementForm(),
        }
        return TemplateResponse(request, "settings/announcements.html", data)
