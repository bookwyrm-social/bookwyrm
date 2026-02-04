"""Populate suggested users"""

from django.core.management.base import BaseCommand

from bookwyrm import models
from bookwyrm.suggested_users import rerank_suggestions_task


def populate_suggestions():
    """build all the streams for all the users"""
    users = models.User.objects.filter(
        local=True,
        is_active=True,
    ).values_list("id", flat=True)
    for user in users:
        rerank_suggestions_task.delay(user)


class Command(BaseCommand):
    """start all over with user suggestions"""

    help = "Populate suggested users for all users"

    def handle(self, *args, **options):
        """run builder"""
        populate_suggestions()
