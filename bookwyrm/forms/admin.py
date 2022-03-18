""" using django model forms """
import datetime

from django import forms
from django.forms import widgets
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_celery_beat.models import IntervalSchedule

from bookwyrm import models
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
class ExpiryWidget(widgets.Select):
    def value_from_datadict(self, data, files, name):
        """human-readable exiration time buckets"""
        selected_string = super().value_from_datadict(data, files, name)

        if selected_string == "day":
            interval = datetime.timedelta(days=1)
        elif selected_string == "week":
            interval = datetime.timedelta(days=7)
        elif selected_string == "month":
            interval = datetime.timedelta(days=31)  # Close enough?
        elif selected_string == "forever":
            return None
        else:
            return selected_string  # This will raise

        return timezone.now() + interval


class CreateInviteForm(CustomForm):
    class Meta:
        model = models.SiteInvite
        exclude = ["code", "user", "times_used", "invitees"]
        widgets = {
            "expiry": ExpiryWidget(
                choices=[
                    ("day", _("One Day")),
                    ("week", _("One Week")),
                    ("month", _("One Month")),
                    ("forever", _("Does Not Expire")),
                ]
            ),
            "use_limit": widgets.Select(
                choices=[(i, _(f"{i} uses")) for i in [1, 5, 10, 25, 50, 100]]
                + [(None, _("Unlimited"))]
            ),
        }


class SiteForm(CustomForm):
    class Meta:
        model = models.SiteSettings
        exclude = ["admin_code", "install_mode"]
        widgets = {
            "instance_short_description": forms.TextInput(
                attrs={"aria-describedby": "desc_instance_short_description"}
            ),
            "require_confirm_email": forms.CheckboxInput(
                attrs={"aria-describedby": "desc_require_confirm_email"}
            ),
            "invite_request_text": forms.Textarea(
                attrs={"aria-describedby": "desc_invite_request_text"}
            ),
        }


class ThemeForm(CustomForm):
    class Meta:
        model = models.Theme
        fields = ["name", "path"]
        widgets = {
            "name": forms.TextInput(attrs={"aria-describedby": "desc_name"}),
            "path": forms.TextInput(
                attrs={
                    "aria-describedby": "desc_path",
                    "placeholder": "css/themes/theme-name.scss",
                }
            ),
        }


class AnnouncementForm(CustomForm):
    class Meta:
        model = models.Announcement
        exclude = ["remote_id"]
        widgets = {
            "preview": forms.TextInput(attrs={"aria-describedby": "desc_preview"}),
            "content": forms.Textarea(attrs={"aria-describedby": "desc_content"}),
            "event_date": forms.SelectDateWidget(
                attrs={"aria-describedby": "desc_event_date"}
            ),
            "start_date": forms.SelectDateWidget(
                attrs={"aria-describedby": "desc_start_date"}
            ),
            "end_date": forms.SelectDateWidget(
                attrs={"aria-describedby": "desc_end_date"}
            ),
            "active": forms.CheckboxInput(attrs={"aria-describedby": "desc_active"}),
        }


class EmailBlocklistForm(CustomForm):
    class Meta:
        model = models.EmailBlocklist
        fields = ["domain"]
        widgets = {
            "avatar": forms.TextInput(attrs={"aria-describedby": "desc_domain"}),
        }


class IPBlocklistForm(CustomForm):
    class Meta:
        model = models.IPBlocklist
        fields = ["address"]


class ServerForm(CustomForm):
    class Meta:
        model = models.FederatedServer
        exclude = ["remote_id"]


class AutoModRuleForm(CustomForm):
    class Meta:
        model = models.AutoMod
        fields = ["string_match", "flag_users", "flag_statuses", "created_by"]


class IntervalScheduleForm(CustomForm):
    class Meta:
        model = IntervalSchedule
        fields = ["every", "period"]

        widgets = {
            "every": forms.NumberInput(attrs={"aria-describedby": "desc_every"}),
            "period": forms.Select(attrs={"aria-describedby": "desc_period"}),
        }
