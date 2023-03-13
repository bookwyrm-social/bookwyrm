""" model for tags """
from bookwyrm import activitypub
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from .fields import CICharField


class Hashtag(ActivitypubMixin, BookWyrmModel):
    "a hashtag which can be used in statuses"

    name = CICharField(
        max_length=256,
        blank=False,
        null=False,
        activitypub_field="name",
        deduplication_field=True,
    )

    name_field = "name"
    activity_serializer = activitypub.Hashtag

    def __repr__(self):
        return f"<{self.__class__} id={self.id} name={self.name}>"
