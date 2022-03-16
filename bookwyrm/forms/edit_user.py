""" using django model forms """
from django import forms

from bookwyrm import models
from bookwyrm.models.fields import ClearableFileInputWithWarning
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
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
            "hide_follows",
            "preferred_timezone",
            "preferred_language",
            "theme",
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
