"""using django model forms"""

from bookwyrm import models
from .custom_form import CustomForm


class UserGroupForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["groups"]
