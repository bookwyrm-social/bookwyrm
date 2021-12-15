""" template filters """
from django import template

from bookwyrm import models

register = template.Library()


@register.filter(name="has_groups")
def has_groups(user):
    """whether or not the user has a pending invitation to join this group"""

    return models.GroupMember.objects.filter(user=user).exists()


@register.filter(name="is_member")
def is_member(group, user):
    """whether or not the user is a member of this group"""

    return models.GroupMember.objects.filter(group=group, user=user).exists()


@register.filter(name="is_invited")
def is_invited(group, user):
    """whether or not the user has a pending invitation to join this group"""

    return models.GroupMemberInvitation.objects.filter(group=group, user=user).exists()
