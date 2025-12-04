"""Forms for Readwise integration settings"""

from django import forms
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from .custom_form import CustomForm


class ReadwiseSettingsForm(CustomForm):
    """Form for configuring Readwise integration"""

    class Meta:
        model = models.User
        fields = [
            "readwise_token",
            "readwise_auto_export",
        ]
        help_texts = {
            "readwise_token": _(
                "Get your token from readwise.io/access_token"
            ),
            "readwise_auto_export": _(
                "Automatically export new quotes to Readwise when you create them"
            ),
        }
        widgets = {
            "readwise_token": forms.PasswordInput(
                attrs={
                    "aria-describedby": "desc_readwise_token",
                    "autocomplete": "off",
                    "placeholder": _("Paste your Readwise API token"),
                },
                render_value=True,
            ),
            "readwise_auto_export": forms.CheckboxInput(
                attrs={"aria-describedby": "desc_readwise_auto_export"}
            ),
        }

    def clean_readwise_token(self):
        """Validate the Readwise token if provided"""
        token = self.cleaned_data.get("readwise_token")
        if token:
            # Strip whitespace
            token = token.strip()
            if token:
                # Validate the token by calling Readwise API
                from bookwyrm.connectors.readwise import ReadwiseClient, ReadwiseAPIError

                client = ReadwiseClient(token)
                if not client.validate_token():
                    raise forms.ValidationError(
                        _("Invalid Readwise API token. Please check and try again.")
                    )
        return token or None
