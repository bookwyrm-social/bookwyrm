""" Forms for the landing pages """
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

import pyotp

from bookwyrm import models
from bookwyrm.settings import DOMAIN
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
class LoginForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["localname", "password"]
        help_texts = {f: None for f in fields}
        widgets = {
            "password": forms.PasswordInput(),
        }

    def infer_username(self):
        """Users may enter their localname, username, or email"""
        localname = self.data.get("localname")
        if "@" in localname:  # looks like an email address to me
            try:
                return models.User.objects.get(email=localname).username
            except models.User.DoesNotExist:  # maybe it's a full username?
                return localname
        return f"{localname}@{DOMAIN}"

    def add_invalid_password_error(self):
        """We don't want to be too specific about this"""
        # pylint: disable=attribute-defined-outside-init
        self.non_field_errors = _("Username or password are incorrect")


class RegisterForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["localname", "email", "password"]
        help_texts = {f: None for f in fields}
        widgets = {"password": forms.PasswordInput()}

    def clean(self):
        """Check if the username is taken"""
        cleaned_data = super().clean()
        localname = cleaned_data.get("localname").strip()
        try:
            validate_password(cleaned_data.get("password"))
        except ValidationError as err:
            self.add_error("password", err)
        if models.User.objects.filter(localname=localname).first():
            self.add_error("localname", _("User with this username already exists"))


class InviteRequestForm(CustomForm):
    def clean(self):
        """make sure the email isn't in use by a registered user"""
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        if email and models.User.objects.filter(email=email).exists():
            self.add_error("email", _("A user with this email already exists."))

    class Meta:
        model = models.InviteRequest
        fields = ["email", "answer"]


class PasswordResetForm(CustomForm):
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = models.User
        fields = ["password"]
        widgets = {
            "password": forms.PasswordInput(),
        }

    def clean(self):
        """Make sure the passwords match and are valid"""
        cleaned_data = super().clean()
        new_password = cleaned_data.get("password")
        confirm_password = self.data.get("confirm_password")

        if new_password != confirm_password:
            self.add_error("confirm_password", _("Password does not match"))

        try:
            validate_password(new_password)
        except ValidationError as err:
            self.add_error("password", err)


class Confirm2FAForm(CustomForm):
    otp = forms.CharField(
        max_length=6, min_length=6, widget=forms.TextInput(attrs={"autofocus": True})
    )

    class Meta:
        model = models.User
        fields = ["otp_secret", "hotp_count"]

    def clean_otp(self):
        """Check otp matches"""
        otp = self.data.get("otp")
        totp = pyotp.TOTP(self.instance.otp_secret)

        if not totp.verify(otp):

            if self.instance.hotp_secret:
                # maybe it's a backup code?
                hotp = pyotp.HOTP(self.instance.hotp_secret)
                hotp_count = (
                    self.instance.hotp_count
                    if self.instance.hotp_count is not None
                    else 0
                )

                if not hotp.verify(otp, hotp_count):
                    self.add_error("otp", _("Incorrect code"))

                # increment the user hotp_count
                else:
                    self.instance.hotp_count = hotp_count + 1
                    self.instance.save(broadcast=False, update_fields=["hotp_count"])

            else:
                self.add_error("otp", _("Incorrect code"))
