""" using django model forms """
from bookwyrm import models
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
class UserGroupForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["groups"]


class GroupForm(CustomForm):
    class Meta:
        model = models.Group
        fields = ["user", "privacy", "name", "description"]
