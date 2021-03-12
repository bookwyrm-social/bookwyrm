""" using django model forms """
import datetime
from collections import defaultdict

from django import forms
from django.forms import ModelForm, PasswordInput, widgets
from django.forms.widgets import Textarea
from django.utils import timezone
from django.utils.translation import gettext as _

from bookwyrm import models


class CustomForm(ModelForm):
    """ add css classes to the forms """

    def __init__(self, *args, **kwargs):
        css_classes = defaultdict(lambda: "")
        css_classes["text"] = "input"
        css_classes["password"] = "input"
        css_classes["email"] = "input"
        css_classes["number"] = "input"
        css_classes["checkbox"] = "checkbox"
        css_classes["textarea"] = "textarea"
        super(CustomForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            if hasattr(visible.field.widget, "input_type"):
                input_type = visible.field.widget.input_type
            if isinstance(visible.field.widget, Textarea):
                input_type = "textarea"
                visible.field.widget.attrs["cols"] = None
                visible.field.widget.attrs["rows"] = None
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
        fields = ["user", "book", "content", "content_warning", "sensitive", "privacy"]


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


class EditUserForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["avatar", "name", "email", "summary", "manually_approves_followers"]
        help_texts = {f: None for f in fields}


class TagForm(CustomForm):
    class Meta:
        model = models.Tag
        fields = ["name"]
        help_texts = {f: None for f in fields}
        labels = {"name": "Add a tag"}


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
            "subjects",  # TODO
            "subject_places",  # TODO
            "connector",
        ]


class AuthorForm(CustomForm):
    class Meta:
        model = models.Author
        exclude = [
            "remote_id",
            "origin_id",
            "created_date",
            "updated_date",
        ]


class ImportForm(forms.Form):
    csv_file = forms.FileField()


class ExpiryWidget(widgets.Select):
    def value_from_datadict(self, data, files, name):
        """ human-readable exiration time buckets """
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
            return selected_string  # "This will raise

        return timezone.now() + interval


class CreateInviteForm(CustomForm):
    class Meta:
        model = models.SiteInvite
        exclude = ["code", "user", "times_used"]
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
                choices=[
                    (i, _("%(count)d uses" % {"count": i}))
                    for i in [1, 5, 10, 25, 50, 100]
                ]
                + [(None, _("Unlimited"))]
            ),
        }


class ShelfForm(CustomForm):
    class Meta:
        model = models.Shelf
        fields = ["user", "name", "privacy"]


class GoalForm(CustomForm):
    class Meta:
        model = models.AnnualGoal
        fields = ["user", "year", "goal", "privacy"]


class SiteForm(CustomForm):
    class Meta:
        model = models.SiteSettings
        exclude = []


class ListForm(CustomForm):
    class Meta:
        model = models.List
        fields = ["user", "name", "description", "curation", "privacy"]
