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

    def action(self):
        """usually we just want to update and save"""
        # self.object may return None if the object is invalid in an expected way
        # ie, Question type
        if self.object:
            self.object.to_model()


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

    to: List[str]
    cc: List[str] = field(default_factory=lambda: [])
    type: str = "Delete"

    def action(self):
        """find and delete the activity object"""
        if not self.object:
            return

        if isinstance(self.object, str):
            # Deleted users are passed as strings. Not wild about this fix
            model = apps.get_model("bookwyrm.User")
            obj = model.find_existing_by_remote_id(self.object)
        else:
            obj = self.object.to_model(save=False, allow_create=False)

        if obj:
            obj.delete()
        # if we can't find it, we don't need to delete it because we don't have it


@dataclass(init=False)
class Update(Verb):
    """Update activity"""

    to: List[str]
    type: str = "Update"

    def action(self):
        """update a model instance from the dataclass"""
        if self.object:
            self.object.to_model(allow_create=False)


@dataclass(init=False)
class Undo(Verb):
    """Undo an activity"""

    type: str = "Undo"

    def action(self):
        """find and remove the activity object"""
        if isinstance(self.object, str):
            # it may be that sometihng should be done with these, but idk what
            # this seems just to be coming from pleroma
            return

        # this is so hacky but it does make it work....
        # (because you Reject a request and Undo a follow
        model = None
        if self.object.type == "Follow":
            model = apps.get_model("bookwyrm.UserFollows")
            obj = self.object.to_model(model=model, save=False, allow_create=False)
            if not obj:
                # this could be a folloq request not a follow proper
                model = apps.get_model("bookwyrm.UserFollowRequest")
                obj = self.object.to_model(model=model, save=False, allow_create=False)
        else:
            obj = self.object.to_model(model=model, save=False, allow_create=False)
        if not obj:
            # if we don't have the object, we can't undo it. happens a lot with boosts
            return
        obj.delete()


@dataclass(init=False)
class Follow(Verb):
    """Follow activity"""

    object: str
    type: str = "Follow"

    def action(self):
        """relationship save"""
        self.to_model()


@dataclass(init=False)
class Block(Verb):
    """Block activity"""

    object: str
    type: str = "Block"

    def action(self):
        """relationship save"""
        self.to_model()


@dataclass(init=False)
class Accept(Verb):
    """Accept activity"""

    object: Follow
    type: str = "Accept"

    def action(self):
        """find and remove the activity object"""
        obj = self.object.to_model(save=False, allow_create=False)
        obj.accept()


@dataclass(init=False)
class Reject(Verb):
    """Reject activity"""

    object: Follow
    type: str = "Reject"

    def action(self):
        """find and remove the activity object"""
        obj = self.object.to_model(save=False, allow_create=False)
        obj.reject()


@dataclass(init=False)
class Add(Verb):
    """Add activity"""

    target: ActivityObject
    object: CollectionItem
    type: str = "Add"

    def action(self):
        """figure out the target to assign the item to a collection"""
        target = resolve_remote_id(self.target)
        item = self.object.to_model(save=False)
        setattr(item, item.collection_field, target)
        item.save()


@dataclass(init=False)
class Remove(Add):
    """Remove activity"""

    type: str = "Remove"

    def action(self):
        """find and remove the activity object"""
        obj = self.object.to_model(save=False, allow_create=False)
        if obj:
            obj.delete()


@dataclass(init=False)
class Like(Verb):
    """a user faving an object"""

    object: str
    type: str = "Like"

    def action(self):
        """like"""
        self.to_model()


@dataclass(init=False)
class Announce(Verb):
    """boosting a status"""

    published: str
    to: List[str] = field(default_factory=lambda: [])
    cc: List[str] = field(default_factory=lambda: [])
    object: str
    type: str = "Announce"

    def action(self):
        """boost"""
        self.to_model()
