"""using django model forms"""

from bookwyrm import models
from .custom_form import CustomForm


class GroupForm(CustomForm):
    class Meta:
        model = models.Group
        fields = ["user", "privacy", "name", "description"]
