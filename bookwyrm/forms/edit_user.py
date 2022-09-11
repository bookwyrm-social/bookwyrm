""" using django model forms """
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from bookwyrm.models.fields import ClearableFileInputWithWarning
from .custom_form import CustomForm

import pyotp

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


class Confirm2FAForm(CustomForm):
    otp = forms.CharField(max_length=6, min_length=6, widget=forms.TextInput)

    # IDK if we need this?
    class Meta:
        model = models.User
        fields = ["otp_secret"]

    def clean(self):
        """Check otp matches"""
        otp = self.data.get("otp")
        totp = pyotp.TOTP(self.instance.otp_secret)

        if not totp.verify(otp):
            # maybe it's a backup code?
            hotp = pyotp.HOTP(self.instance.otp_secret)
            hotp_count = (
                self.instance.hotp_count if self.instance.hotp_count is not None else 0
            )

            if not hotp.verify(otp, hotp_count):
                self.add_error("otp", _("Code does not match"))

            # TODO: backup codes
            # increment the user hotp_count if it was an HOTP
            # self.instance.hotp_count = hotp_count + 1
            # self.instance.save(broadcast=False, update_fields=["hotp_count"])
