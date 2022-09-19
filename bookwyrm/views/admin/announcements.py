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
        # pylint: disable=consider-using-f-string
        if sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            announcements = announcements.order_by(sort)
        data = {
            "announcements": Paginator(announcements, PAGE_LENGTH).get_page(
                request.GET.get("page")
            ),
            "form": forms.AnnouncementForm(),
            "sort": sort,
        }
        return TemplateResponse(
            request, "settings/announcements/announcements.html", data
        )


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
        }
        return TemplateResponse(
            request, "settings/announcements/announcement.html", data
        )


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class EditAnnouncement(View):
    """Create of edit an announcement"""

    def get(self, request, announcement_id=None):
        """announcement forms"""
        announcement = None
        if announcement_id:
            announcement = get_object_or_404(models.Announcement, id=announcement_id)

        data = {
            "announcement": announcement,
            "form": forms.AnnouncementForm(instance=announcement),
        }
        return TemplateResponse(
            request, "settings/announcements/edit_announcement.html", data
        )

    def post(self, request, announcement_id=None):
        """edit announcement"""
        announcement = None
        if announcement_id:
            announcement = get_object_or_404(models.Announcement, id=announcement_id)

        form = forms.AnnouncementForm(request.POST, instance=announcement)
        if not form.is_valid():
            data = {
                "announcement": announcement,
                "form": form,
            }
            return TemplateResponse(
                request, "settings/announcements/edit_announcement.html", data
            )
        announcement = form.save(request)
        return redirect("settings-announcements", announcement.id)


@login_required
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def delete_announcement(_, announcement_id):
    """delete announcement"""
    announcement = get_object_or_404(models.Announcement, id=announcement_id)
    announcement.delete()
    return redirect("settings-announcements")
