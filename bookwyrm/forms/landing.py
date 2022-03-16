""" Forms for the landing pages """
from django.forms import PasswordInput
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
            "password": PasswordInput(),
        }


class RegisterForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["localname", "email", "password"]
        help_texts = {f: None for f in fields}
        widgets = {"password": PasswordInput()}

    def clean(self):
        """Check if the username is taken"""
        cleaned_data = super().clean()
        localname = cleaned_data.get("localname").strip()
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
