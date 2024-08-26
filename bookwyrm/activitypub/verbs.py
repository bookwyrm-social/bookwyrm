""" activities that do things """
from dataclasses import dataclass, field
from typing import List
from django.apps import apps

from .base_activity import ActivityObject, Signature, resolve_remote_id
from .ordered_collection import CollectionItem


@dataclass(init=False)
class Verb(ActivityObject):
    """generic fields for activities"""

    actor: str
    object: ActivityObject

    def action(self, allow_external_connections=True):
        """usually we just want to update and save"""
        # self.object may return None if the object is invalid in an expected way
        # ie, Question type
        if self.object:
            self.object.to_model(allow_external_connections=allow_external_connections)


@dataclass(init=False)
class Create(Verb):
    """Create activity"""

    to: List[str]
    cc: List[str] = field(default_factory=lambda: [])
    signature: Signature = None
    type: str = "Create"


@dataclass(init=False)
class Delete(Verb):
    """Create activity"""

    to: List[str] = field(default_factory=lambda: [])
    cc: List[str] = field(default_factory=lambda: [])
    type: str = "Delete"

    def action(self, allow_external_connections=True):
        """find and delete the activity object"""
        if not self.object:
            return

        if isinstance(self.object, str):
            # Deleted users are passed as strings. Not wild about this fix
            model = apps.get_model("bookwyrm.User")
            obj = model.find_existing_by_remote_id(self.object)
        else:
            obj = self.object.to_model(
                save=False,
                allow_create=False,
                allow_external_connections=allow_external_connections,
            )

        if obj:
            obj.delete()
        # if we can't find it, we don't need to delete it because we don't have it


@dataclass(init=False)
class Update(Verb):
    """Update activity"""

    to: List[str]
    type: str = "Update"

    def action(self, allow_external_connections=True):
        """update a model instance from the dataclass"""
        if not self.object:
            return
        self.object.to_model(
            allow_create=False, allow_external_connections=allow_external_connections
        )


@dataclass(init=False)
class Undo(Verb):
    """Undo an activity"""

    type: str = "Undo"

    def action(self, allow_external_connections=True):
        """find and remove the activity object"""
        if isinstance(self.object, str):
            # it may be that something should be done with these, but idk what
            # this seems just to be coming from pleroma
            return

        # this is so hacky but it does make it work....
        # (because you Reject a request and Undo a follow
        model = None
        if self.object.type == "Follow":
            model = apps.get_model("bookwyrm.UserFollows")
            obj = self.object.to_model(
                model=model,
                save=False,
                allow_create=False,
                allow_external_connections=allow_external_connections,
            )
            if not obj:
                # this could be a follow request not a follow proper
                model = apps.get_model("bookwyrm.UserFollowRequest")
                obj = self.object.to_model(
                    model=model,
                    save=False,
                    allow_create=False,
                    allow_external_connections=allow_external_connections,
                )
        else:
            obj = self.object.to_model(
                model=model,
                save=False,
                allow_create=False,
                allow_external_connections=allow_external_connections,
            )
        if not obj:
            # if we don't have the object, we can't undo it. happens a lot with boosts
            return
        obj.delete()


@dataclass(init=False)
class Follow(Verb):
    """Follow activity"""

    object: str
    type: str = "Follow"

    def action(self, allow_external_connections=True):
        """relationship save"""
        self.to_model(allow_external_connections=allow_external_connections)


@dataclass(init=False)
class Block(Verb):
    """Block activity"""

    object: str
    type: str = "Block"

    def action(self, allow_external_connections=True):
        """relationship save"""
        self.to_model(allow_external_connections=allow_external_connections)


@dataclass(init=False)
class Accept(Verb):
    """Accept activity"""

    object: Follow
    type: str = "Accept"

    def action(self, allow_external_connections=True):
        """accept a request"""
        obj = self.object.to_model(save=False, allow_create=True)
        obj.accept()


@dataclass(init=False)
class Reject(Verb):
    """Reject activity"""

    object: Follow
    type: str = "Reject"

    def action(self, allow_external_connections=True):
        """reject a follow or follow request"""

        for model_name in ["UserFollowRequest", "UserFollows", None]:
            model = apps.get_model(f"bookwyrm.{model_name}") if model_name else None
            if obj := self.object.to_model(
                model=model,
                save=False,
                allow_create=False,
                allow_external_connections=allow_external_connections,
            ):
                # Reject the first model that can be built.
                obj.reject()
                break


@dataclass(init=False)
class Add(Verb):
    """Add activity"""

    target: ActivityObject
    object: CollectionItem
    type: str = "Add"

    def action(self, allow_external_connections=True):
        """figure out the target to assign the item to a collection"""
        target = resolve_remote_id(self.target)
        item = self.object.to_model(save=False)
        setattr(item, item.collection_field, target)
        item.save()


@dataclass(init=False)
class Remove(Add):
    """Remove activity"""

    type: str = "Remove"

    def action(self, allow_external_connections=True):
        """find and remove the activity object"""
        obj = self.object.to_model(save=False, allow_create=False)
        if obj:
            obj.delete()


@dataclass(init=False)
class Like(Verb):
    """a user faving an object"""

    object: str
    type: str = "Like"

    def action(self, allow_external_connections=True):
        """like"""
        self.to_model(allow_external_connections=allow_external_connections)


@dataclass(init=False)
class Announce(Verb):
    """boosting a status"""

    published: str
    to: List[str] = field(default_factory=lambda: [])
    cc: List[str] = field(default_factory=lambda: [])
    object: str
    type: str = "Announce"

    def action(self, allow_external_connections=True):
        """boost"""
        self.to_model(allow_external_connections=allow_external_connections)


@dataclass(init=False)
class Move(Verb):
    """a user moving an object"""

    object: str
    type: str = "Move"
    origin: str = None
    target: str = None

    def action(self, allow_external_connections=True):
        """move"""

        object_is_user = resolve_remote_id(remote_id=self.object, model="User")

        if object_is_user:
            model = apps.get_model("bookwyrm.MoveUser")

            self.to_model(
                model=model,
                save=True,
                allow_external_connections=allow_external_connections,
            )
        else:
            # we might do something with this to move other objects at some point
            pass
