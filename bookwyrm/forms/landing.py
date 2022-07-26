""" Forms for the landing pages """
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
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
