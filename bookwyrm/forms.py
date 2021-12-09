""" using django model forms """
import datetime
from collections import defaultdict

from django import forms
from django.forms import ModelForm, PasswordInput, widgets, ChoiceField
from django.forms.widgets import Textarea
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from bookwyrm.models.fields import ClearableFileInputWithWarning
from bookwyrm.models.user import FeedFilterChoices


class CustomForm(ModelForm):
    """add css classes to the forms"""

    def __init__(self, *args, **kwargs):
        css_classes = defaultdict(lambda: "")
        css_classes["text"] = "input"
        css_classes["password"] = "input"
        css_classes["email"] = "input"
        css_classes["number"] = "input"
        css_classes["checkbox"] = "checkbox"
        css_classes["textarea"] = "textarea"
        # pylint: disable=super-with-arguments
        super(CustomForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            if hasattr(visible.field.widget, "input_type"):
                input_type = visible.field.widget.input_type
            if isinstance(visible.field.widget, Textarea):
                input_type = "textarea"
                visible.field.widget.attrs["rows"] = 5
            visible.field.widget.attrs["class"] = css_classes[input_type]


# pylint: disable=missing-class-docstring
class LoginForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["localname", "password"]
        help_texts = {f: None for f in fields}
        widgets = {
            "password": PasswordInput(),
        }


class RegisterForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["localname", "email", "password"]
        help_texts = {f: None for f in fields}
        widgets = {"password": PasswordInput()}


class RatingForm(CustomForm):
    class Meta:
        model = models.ReviewRating
        fields = ["user", "book", "rating", "privacy"]


class ReviewForm(CustomForm):
    class Meta:
        model = models.Review
        fields = [
            "user",
            "book",
            "name",
            "content",
            "rating",
            "content_warning",
            "sensitive",
            "privacy",
        ]


class CommentForm(CustomForm):
    class Meta:
        model = models.Comment
        fields = [
            "user",
            "book",
            "content",
            "content_warning",
            "sensitive",
            "privacy",
            "progress",
            "progress_mode",
            "reading_status",
        ]


class QuotationForm(CustomForm):
    class Meta:
        model = models.Quotation
        fields = [
            "user",
            "book",
            "quote",
            "content",
            "content_warning",
            "sensitive",
            "privacy",
            "position",
            "position_mode",
        ]


class ReplyForm(CustomForm):
    class Meta:
        model = models.Status
        fields = [
            "user",
            "content",
            "content_warning",
            "sensitive",
            "reply_parent",
            "privacy",
        ]


class StatusForm(CustomForm):
    class Meta:
        model = models.Status
        fields = ["user", "content", "content_warning", "sensitive", "privacy"]


class DirectForm(CustomForm):
    class Meta:
        model = models.Status
        fields = ["user", "content", "content_warning", "sensitive", "privacy"]


class EditUserForm(CustomForm):
    class Meta:
        model = models.User
        fields = [
            "avatar",
            "name",
            "email",
            "summary",
            "show_goal",
            "show_suggested_users",
            "manually_approves_followers",
            "default_post_privacy",
            "discoverable",
            "preferred_timezone",
            "preferred_language",
        ]
        help_texts = {f: None for f in fields}
        widgets = {
            "avatar": ClearableFileInputWithWarning(
                attrs={"aria-describedby": "desc_avatar"}
            ),
            "name": forms.TextInput(attrs={"aria-describedby": "desc_name"}),
            "summary": forms.Textarea(attrs={"aria-describedby": "desc_summary"}),
            "email": forms.EmailInput(attrs={"aria-describedby": "desc_email"}),
            "discoverable": forms.CheckboxInput(
                attrs={"aria-describedby": "desc_discoverable"}
            ),
        }


class LimitedEditUserForm(CustomForm):
    class Meta:
        model = models.User
        fields = [
            "avatar",
            "name",
            "summary",
            "manually_approves_followers",
            "discoverable",
        ]
        help_texts = {f: None for f in fields}
        widgets = {
            "avatar": ClearableFileInputWithWarning(
                attrs={"aria-describedby": "desc_avatar"}
            ),
            "name": forms.TextInput(attrs={"aria-describedby": "desc_name"}),
            "summary": forms.Textarea(attrs={"aria-describedby": "desc_summary"}),
            "discoverable": forms.CheckboxInput(
                attrs={"aria-describedby": "desc_discoverable"}
            ),
        }


class DeleteUserForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["password"]


class UserGroupForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["groups"]


class FeedStatusTypesForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["feed_status_types"]
        help_texts = {f: None for f in fields}
        widgets = {
            "feed_status_types": widgets.CheckboxSelectMultiple(
                choices=FeedFilterChoices,
            ),
        }


class CoverForm(CustomForm):
    class Meta:
        model = models.Book
        fields = ["cover"]
        help_texts = {f: None for f in fields}


class EditionForm(CustomForm):
    class Meta:
        model = models.Edition
        exclude = [
            "remote_id",
            "origin_id",
            "created_date",
            "updated_date",
            "edition_rank",
            "authors",
            "parent_work",
            "shelves",
            "connector",
            "search_vector",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"aria-describedby": "desc_title"}),
            "subtitle": forms.TextInput(attrs={"aria-describedby": "desc_subtitle"}),
            "description": forms.Textarea(
                attrs={"aria-describedby": "desc_description"}
            ),
            "series": forms.TextInput(attrs={"aria-describedby": "desc_series"}),
            "series_number": forms.TextInput(
                attrs={"aria-describedby": "desc_series_number"}
            ),
            "languages": forms.TextInput(
                attrs={"aria-describedby": "desc_languages_help desc_languages"}
            ),
            "publishers": forms.TextInput(
                attrs={"aria-describedby": "desc_publishers_help desc_publishers"}
            ),
            "first_published_date": forms.SelectDateWidget(
                attrs={"aria-describedby": "desc_first_published_date"}
            ),
            "published_date": forms.SelectDateWidget(
                attrs={"aria-describedby": "desc_published_date"}
            ),
            "cover": ClearableFileInputWithWarning(
                attrs={"aria-describedby": "desc_cover"}
            ),
            "physical_format": forms.Select(
                attrs={"aria-describedby": "desc_physical_format"}
            ),
            "physical_format_detail": forms.TextInput(
                attrs={"aria-describedby": "desc_physical_format_detail"}
            ),
            "pages": forms.NumberInput(attrs={"aria-describedby": "desc_pages"}),
            "isbn_13": forms.TextInput(attrs={"aria-describedby": "desc_isbn_13"}),
            "isbn_10": forms.TextInput(attrs={"aria-describedby": "desc_isbn_10"}),
            "openlibrary_key": forms.TextInput(
                attrs={"aria-describedby": "desc_openlibrary_key"}
            ),
            "inventaire_id": forms.TextInput(
                attrs={"aria-describedby": "desc_inventaire_id"}
            ),
            "oclc_number": forms.TextInput(
                attrs={"aria-describedby": "desc_oclc_number"}
            ),
            "ASIN": forms.TextInput(attrs={"aria-describedby": "desc_ASIN"}),
        }


class AuthorForm(CustomForm):
    class Meta:
        model = models.Author
        fields = [
            "last_edited_by",
            "name",
            "aliases",
            "bio",
            "wikipedia_link",
            "born",
            "died",
            "openlibrary_key",
            "inventaire_id",
            "librarything_key",
            "goodreads_key",
            "isni",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"aria-describedby": "desc_name"}),
            "aliases": forms.TextInput(attrs={"aria-describedby": "desc_aliases"}),
            "bio": forms.Textarea(attrs={"aria-describedby": "desc_bio"}),
            "wikipedia_link": forms.TextInput(
                attrs={"aria-describedby": "desc_wikipedia_link"}
            ),
            "born": forms.SelectDateWidget(attrs={"aria-describedby": "desc_born"}),
            "died": forms.SelectDateWidget(attrs={"aria-describedby": "desc_died"}),
            "oepnlibrary_key": forms.TextInput(
                attrs={"aria-describedby": "desc_oepnlibrary_key"}
            ),
            "inventaire_id": forms.TextInput(
                attrs={"aria-describedby": "desc_inventaire_id"}
            ),
            "librarything_key": forms.TextInput(
                attrs={"aria-describedby": "desc_librarything_key"}
            ),
            "goodreads_key": forms.TextInput(
                attrs={"aria-describedby": "desc_goodreads_key"}
            ),
        }


class ImportForm(forms.Form):
    csv_file = forms.FileField()


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


class InviteRequestForm(CustomForm):
    def clean(self):
        """make sure the email isn't in use by a registered user"""
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        if email and models.User.objects.filter(email=email).exists():
            self.add_error("email", _("A user with this email already exists."))

    class Meta:
        model = models.InviteRequest
        fields = ["email"]


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


class ShelfForm(CustomForm):
    class Meta:
        model = models.Shelf
        fields = ["user", "name", "privacy", "description"]


class GoalForm(CustomForm):
    class Meta:
        model = models.AnnualGoal
        fields = ["user", "year", "goal", "privacy"]


class SiteForm(CustomForm):
    class Meta:
        model = models.SiteSettings
        exclude = []
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


class ListForm(CustomForm):
    class Meta:
        model = models.List
        fields = ["user", "name", "description", "curation", "privacy", "group"]


class GroupForm(CustomForm):
    class Meta:
        model = models.Group
        fields = ["user", "privacy", "name", "description"]


class ReportForm(CustomForm):
    class Meta:
        model = models.Report
        fields = ["user", "reporter", "statuses", "note"]


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


class SortListForm(forms.Form):
    sort_by = ChoiceField(
        choices=(
            ("order", _("List Order")),
            ("title", _("Book Title")),
            ("rating", _("Rating")),
        ),
        label=_("Sort By"),
    )
    direction = ChoiceField(
        choices=(
            ("ascending", _("Ascending")),
            ("descending", _("Descending")),
        ),
    )
