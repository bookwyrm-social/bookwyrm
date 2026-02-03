"""model for tags"""

from bookwyrm import activitypub
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from .fields import CharField


class Hashtag(ActivitypubMixin, BookWyrmModel):
    "a hashtag which can be used in statuses"

    name = CharField(
        max_length=256,
        blank=False,
        null=False,
        activitypub_field="name",
        deduplication_field=True,
        db_collation="case_insensitive",
    )

    name_field = "name"
    activity_serializer = activitypub.Hashtag

    def __repr__(self):
        return f"<{self.__class__} id={self.id} name={self.name}>"
