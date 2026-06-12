"""using django model forms"""

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from bookwyrm.models.fields import ClearableFileInputWithWarning
from .custom_form import CustomForm


class EditUserForm(CustomForm):
    readwise_api_key = forms.CharField(
        label=_("Readwise access token"),
        required=False,
        strip=True,
        widget=forms.PasswordInput(
            attrs={"aria-describedby": "desc_readwise_api_key"},
            render_value=False,
        ),
    )
    clear_readwise_api_key = forms.BooleanField(
        label=_("Remove saved Readwise access token"),
        required=False,
    )

    class Meta:
        model = models.User
        fields = [
            "avatar",
            "name",
            "email",
            "summary",
            "show_goal",
            "show_ratings",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.readwise_api_key:
            self.fields["readwise_api_key"].help_text = _(
                "A Readwise access token is saved. Leave this blank to keep it."
            )

    def save(self, request, *args, **kwargs):
        commit = kwargs.get("commit", True)
        user = super().save(request, *args, **kwargs)
        changed = False
        if self.cleaned_data.get("clear_readwise_api_key"):
            user.readwise_api_key = ""
            changed = True
        elif token := self.cleaned_data.get("readwise_api_key"):
            user.readwise_api_key = token
            changed = True
        if changed and commit:
            user.save(update_fields=["readwise_api_key"])
        return user


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


class MoveUserForm(CustomForm):
    target = forms.CharField(widget=forms.TextInput)

    class Meta:
        model = models.User
        fields = ["password"]


class AliasUserForm(CustomForm):
    username = forms.CharField(widget=forms.TextInput)

    class Meta:
        model = models.User
        fields = ["password"]


class ChangePasswordForm(CustomForm):
    current_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = models.User
        fields = ["password"]
        widgets = {
            "password": forms.PasswordInput(),
        }

    def clean(self):
        """Make sure passwords match and are valid"""
        current_password = self.data.get("current_password")
        if not self.instance.check_password(current_password):
            self.add_error("current_password", _("Incorrect password"))

        cleaned_data = super().clean()
        new_password = cleaned_data.get("password")
        confirm_password = self.data.get("confirm_password")

        if new_password != confirm_password:
            self.add_error("confirm_password", _("Password does not match"))

        try:
            validate_password(new_password)
        except ValidationError as err:
            self.add_error("password", err)


class ConfirmPasswordForm(CustomForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = models.User
        fields = ["password"]
        widgets = {
            "password": forms.PasswordInput(),
        }

    def clean(self):
        """Make sure password is correct"""
        password = self.data.get("password")

        if not self.instance.check_password(password):
            self.add_error("password", _("Incorrect Password"))
