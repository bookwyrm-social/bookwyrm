""" do book related things with other users """
from django.apps import apps
from django.db import models
from django.utils import timezone

from bookwyrm.settings import DOMAIN
from .base_model import BookWyrmModel
from . import fields


class Group(BookWyrmModel):
    """A group of users"""

    name = fields.CharField(max_length=100)
    manager = fields.ForeignKey(
        "User", on_delete=models.PROTECT)
    description = fields.TextField(blank=True, null=True)
    privacy = fields.PrivacyField()

    lists = models.ManyToManyField(
        "List",
        symmetrical=False,
        through="GroupList",
        through_fields=("group", "book_list"),
    )

    members = models.ManyToManyField(
        "User",
        symmetrical=False,
        through="GroupMember",
        through_fields=("group", "user"),
        related_name="members"
    )

class GroupList(BookWyrmModel):
    """Lists that group members can edit"""

    group = models.ForeignKey("Group", on_delete=models.CASCADE)
    book_list = models.ForeignKey("List", on_delete=models.CASCADE)

class GroupMember(models.Model):
    """Users who are members of a group"""

    group = models.ForeignKey("Group", on_delete=models.CASCADE)
    user = models.ForeignKey("User", on_delete=models.CASCADE)

    class Meta:
        constraints = [
          models.UniqueConstraint(
            fields=["group", "user"], name="unique_member"
          )
        ]