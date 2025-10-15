""" base model with default fields """
import base64
from Crypto import Random

from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q
from django.dispatch import receiver
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

from bookwyrm.settings import BASE_URL
from .fields import RemoteIdField


DeactivationReason = [
    ("pending", _("Pending")),
    ("self_deletion", _("Self deletion")),
    ("self_deactivation", _("Self deactivation")),
    ("moderator_suspension", _("Moderator suspension")),
    ("moderator_deletion", _("Moderator deletion")),
    ("domain_block", _("Domain block")),
]


def new_access_code():
    """the identifier for a user invite"""
    return base64.b32encode(Random.get_random_bytes(5)).decode("ascii")


class BookWyrmModel(models.Model):
    """shared fields"""

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    remote_id = RemoteIdField(null=True, activitypub_field="id")

    def get_remote_id(self):
        """generate the url that resolves to the local object, without a slug"""
        base_path = BASE_URL
        if hasattr(self, "user"):
            base_path = f"{base_path}{self.user.local_path}"

        model_name = type(self).__name__.lower()
        return f"{base_path}/{model_name}/{self.id}"

    class Meta:
        """this is just here to provide default fields for other models"""

        abstract = True

    @property
    def local_path(self):
        """how to link to this object in the local app, with a slug"""
        local = self.get_remote_id().replace(BASE_URL, "")

        name = None
        if hasattr(self, "name_field"):
            name = getattr(self, self.name_field)
        elif hasattr(self, "name"):
            name = self.name

        if name:
            slug = slugify(name, allow_unicode=True)
            local = f"{local}/s/{slug}"

        return local

    def raise_visible_to_user(self, viewer):
        """is a user authorized to view an object?"""
        # make sure this is an object with privacy owned by a user
        if not hasattr(self, "user") or not hasattr(self, "privacy"):
            return

        # viewer can't see it if the object's owner blocked them
        if viewer in self.user.blocks.all():
            raise Http404()

        # you can see your own posts and any public or unlisted posts
        if viewer == self.user or self.privacy in ["public", "unlisted"]:
            return

        # you can see the followers only posts of people you follow
        if self.privacy == "followers" and (
            self.user.followers.filter(id=viewer.id).first()
        ):
            return

        # you can see dms you are tagged in
        if hasattr(self, "mention_users"):
            if (
                self.privacy in ["direct", "followers"]
                and self.mention_users.filter(id=viewer.id).first()
            ):

                return

        # you can see groups of which you are a member
        if (
            hasattr(self, "memberships")
            and viewer.is_authenticated
            and self.memberships.filter(user=viewer).exists()
        ):
            return

        # you can see objects which have a group of which you are a member
        if hasattr(self, "group"):
            if (
                hasattr(self.group, "memberships")
                and self.group.memberships.filter(user=viewer).exists()
            ):
                return

        raise Http404()

    def raise_not_editable(self, viewer):
        """does this user have permission to edit this object? liable to be overwritten
        by models that inherit this base model class"""
        if not hasattr(self, "user"):
            return

        # generally moderators shouldn't be able to edit other people's stuff
        if self.user == viewer:
            return

        raise PermissionDenied()

    def raise_not_deletable(self, viewer):
        """does this user have permission to delete this object? liable to be
        overwritten by models that inherit this base model class"""
        if not hasattr(self, "user"):
            return

        # but generally moderators can delete other people's stuff
        if self.user == viewer or viewer.has_perm("bookwyrm.moderate_post"):
            return

        raise PermissionDenied()

    @classmethod
    def privacy_filter(cls, viewer, privacy_levels=None):
        """filter objects that have "user" and "privacy" fields"""
        queryset = cls.objects
        if hasattr(queryset, "select_subclasses"):
            queryset = queryset.select_subclasses()

        privacy_levels = privacy_levels or ["public", "unlisted", "followers", "direct"]
        # you can't see followers only or direct messages if you're not logged in
        if viewer.is_anonymous:
            privacy_levels = [
                p for p in privacy_levels if not p in ["followers", "direct"]
            ]
        else:
            # exclude blocks from both directions
            queryset = queryset.exclude(
                Q(user__blocked_by=viewer) | Q(user__blocks=viewer)
            )

        # filter to only provided privacy levels
        queryset = queryset.filter(privacy__in=privacy_levels)

        if "followers" in privacy_levels:
            queryset = cls.followers_filter(queryset, viewer)

        # exclude direct messages not intended for the user
        if "direct" in privacy_levels:
            queryset = cls.direct_filter(queryset, viewer)

        return queryset

    @classmethod
    def followers_filter(cls, queryset, viewer):
        """Override-able filter for "followers" privacy level"""
        return queryset.exclude(
            ~Q(  # user isn't following and it isn't their own status
                Q(user__followers=viewer) | Q(user=viewer)
            ),
            privacy="followers",  # and the status is followers only
        )

    @classmethod
    def direct_filter(cls, queryset, viewer):
        """Override-able filter for "direct" privacy level"""
        return queryset.exclude(~Q(user=viewer), privacy="direct")


@receiver(models.signals.post_save)
# pylint: disable=unused-argument
def set_remote_id(sender, instance, created, *args, **kwargs):
    """set the remote_id after save (when the id is available)"""
    if not created or not hasattr(instance, "get_remote_id"):
        return
    if not instance.remote_id:
        instance.remote_id = instance.get_remote_id()
        try:
            instance.save(broadcast=False)
        except TypeError:
            instance.save()
