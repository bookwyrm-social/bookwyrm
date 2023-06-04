"""Import data from Bookwyrm export files"""
from functools import reduce
import json
import operator

from django.apps import apps
from django.core import serializers
from django.db.models import Q
from django.forms.models import model_to_dict
from django.utils import timezone

from bookwyrm import activitypub, models, settings
from bookwyrm.models.activitypub_mixin import ActivitypubMixin
from bookwyrm.views.books.books import set_cover_from_url


class BookwyrmImporter:
    """Import a Bookwyrm User export JSON file.
    This is kind of a combination of an importer and a connector.
    """

    def process_import(self, user, json_file, settings):
        """import user data from a Bookwyrm export file"""

        import_data = json.load(json_file)

        include_user_profile = settings.get("include_user_profile") == "on"
        include_user_settings = settings.get("include_user_settings") == "on"
        include_goals = settings.get("include_goals") == "on"

        include_shelves = settings.get("include_shelves") == "on"
        include_readthroughs = settings.get("include_readthroughs") == "on"
        include_reviews = settings.get("include_reviews") == "on"
        include_lists = settings.get("include_lists") == "on"

        include_saved_lists = settings.get("include_saved_lists") == "on"
        include_follows = settings.get("include_follows") == "on"

        if include_user_profile:
            self.update_user_profile(user, import_data.get("user"))
        if include_user_settings:
            self.update_user_settings(user, import_data.get("user"))
        if include_goals:
            self.update_goals(user, import_data.get("goals"))

        # Always import books, otherwise we can't do anything else
        self.process_books(
            user=user,
            books_data=import_data.get("books"),
            include_shelves=include_shelves,
            include_readthroughs=include_readthroughs,
            include_reviews=include_reviews,
            include_lists=include_lists,
        )

    def process_books(self, **kwargs):
        """process user import data related to books"""

        for obj in kwargs["books_data"]:

            # create the books. We need to merge Book and Edition instances
            # and also check whether these books already exist in the DB
            des_books = serializers.deserialize("json", obj.get("book"))
            des_editions = serializers.deserialize("json", obj.get("edition"))
            next_book = next(des_books)
            next_edition = next(des_editions)
            book = self.get_or_create_edition(
                {"book": next_book.object, "edition": next_edition.object}
            )
            # Now we have a local book we can add authors
            authors = self.get_or_create_authors(obj["authors"])
            book.authors.set(authors)
            book.save()

            if kwargs["include_shelves"]:
                self.create_parent_child_objects_if_not_exists(
                    models.Shelf, obj.get("shelves"), kwargs["user"], book
                )

            if kwargs["include_readthroughs"]:
                self.get_or_create_simple_objects(
                    models.ReadThrough, obj.get("readthroughs"), kwargs["user"], book
                )

            if kwargs["include_reviews"]:
                self.create_merged_objects_if_not_exists(
                    models.Review, obj.get("lists"), kwargs["user"]
                )

            if kwargs["include_lists"]:
                self.create_parent_child_objects_if_not_exists(
                    models.List, obj.get("lists"), kwargs["user"], book
                )

            if kwargs["include_saved_lists"]:
                # TODO
                pass
            if kwargs["include_follows"]:
                # TODO
                pass

    def update_user_profile(self, user, data):
        """update the user's profile from import data"""

        user.name = data.get("name")
        user.summary = data.get("summary")
        user.save()
        # TODO: would be ideal to include the actual file in the export and make it a tar
        avatar = set_cover_from_url(data.get("avatar"))
        user.avatar.save(*avatar)

    def update_user_settings(self, user, data):
        """update the user's settings from import data"""

        update_fields = [
            "manually_approves_followers",
            "hide_follows",
            "show_goal",
            "show_suggested_users",
            "discoverable",
            "preferred_timezone",
            "default_post_privacy",
        ]

        for field in update_fields:
            setattr(user, field, data.get(field))
        user.save()

    def update_goals(self, user, data):
        """update the user's goals from import data"""

        for goal in data:
            # edit the existing goal if there is one instead of making a new one
            existing = models.AnnualGoal.objects.filter(
                year=goal["year"], user=user
            ).first()
            if existing:
                for k in goal.keys():
                    setattr(existing, k, goal[k])
                existing.save()
            else:
                goal["user"] = user
                models.AnnualGoal.objects.create(**goal)

    def get_or_create_authors(self, data):
        """Take a serialised JSON string of authors
        find or create the authors in the database
        and return a list of author instances"""

        authors = []
        deserialized = serializers.deserialize("json", data)
        for author in deserialized:
            clean = self.clean_values(author.object)
            existing = self.find_existing(models.Author, model_to_dict(clean), None)
            if existing:
                authors.append(existing)
            clean._state.adding = True
            clean.save()
            authors.append(clean)
        return authors

    def get_or_create_edition(self, data):
        """Take a serialised JSON string of books and
        editions, find or create the editions in the
        database and return a list of edotopm instances"""

        book_dict = model_to_dict(data["book"])
        edition_dict = model_to_dict(data["edition"])
        clean = self.clean_values(book_dict)
        keys = [
            "isbn_10",
            "isbn_13",
            "oclc_number",
            "pages",
            "physical_format",
            "physical_format_detail",
            "publishers",
        ]
        for key in keys:
            clean[key] = edition_dict[key]
        existing = self.find_existing(models.Edition, clean, None)
        if existing:
            return existing
        new = models.Edition.objects.create(**clean)
        return new

    def clean_values(self, data):
        """clean values we don't want when creating new instances"""
        values = [
            "id",
            "pk",
            "remote_id",
            "cover",
            "preview_image",
            "authors",
            "last_edited_by",
            "user",
            "book_list",
            "shelf_book",
        ]

        if isinstance(data, dict):
            common = data.keys() & values
            for val in common:
                data[val] = None
                data["id"] = None
        else:
            common = model_to_dict(data).keys() & values
            for val in common:
                setattr(data, val, None)
        return data

    def find_existing(self, cls, data, user):
        """User fields that can be used for deduplication
        to find any existing model instances"""

        identifiers = [
            "openlibrary_key",
            "inventaire_id",
            "librarything_key",
            "goodreads_key",
            "asin",
            "isfdb",
            "isbn_10",
            "isbn_13",
            "oclc_number",
            "origin_id",
            "viaf",
            "wikipedia_link",
            "isni",
            "gutenberg_id",
            "identifier",
        ]

        match_fields = []
        for i in identifiers:
            if i in data and data[i] not in [None, ""]:
                match_fields.append({i: data.get(i)})

        if cls == models.ReadThrough:
            match = cls.objects.filter(book=data["book"], start_date=data["start_date"])
            return match.first()
        if cls == models.List:
            match = cls.objects.filter(name=data["name"], user=user)
            return match.first()
        if cls == models.Shelf:
            match = cls.objects.filter(identifier=data["identifier"], user=user)
            return match.first()
        if cls == models.ListItem:
            match = cls.objects.filter(
                book_list=data["book_list"], book=data["book"], user=user
            )
            return match.first()
        if cls == models.ShelfBook:
            match = cls.objects.filter(
                shelf=data["shelf"], book=data["book"], user=user
            )
            return match.first()
        else:
            if len(match_fields) > 0:
                match = cls.objects.filter(
                    reduce(operator.or_, (Q(**f) for f in match_fields))
                )
                return match.first()
        return None

    def get_or_create_simple_objects(self, model, data, user, book):
        """Take a serialised JSON string of model instances
        find or create the instances in the database
        and return a list of saved instances"""

        deserialized = serializers.deserialize("json", data)
        instances = []
        for rt in deserialized:
            clean = self.clean_values(rt.object)
            existing = self.find_existing(model, model_to_dict(clean), user)
            if existing:
                instances.append(existing)
                continue
            clean._state.adding = True
            clean.user = user
            clean.book = book
            clean.save()
            instances.append(clean)
        return instances

    def create_instance_if_not_exists(self, model, data):
        """Take a model instance and check
        whether is already exists before saving"""
        if model.objects.filter(**data).exists():
            return
        model.objects.create(**data)

    def create_parent_child_objects_if_not_exists(self, cls, data, user, book):
        """Take a serialised JSON string of paired model instances saved together and
        find or create the instances in the database e.g. List/ListItem, Shelf/ShelfBook"""

        deserialized = serializers.deserialize("json", data)
        parents = []
        all_children = []
        for obj in deserialized:
            if obj.object.__class__.__name__ in ["List", "Shelf"]:
                parents.append(obj.object)
            else:
                all_children.append(obj.object)
        for p in parents:

            if cls == models.List:
                children = [c for c in all_children if p.id == c.book_list.id]
            if cls == models.Shelf:
                children = [c for c in all_children if p.id == c.shelf.id]

            clean_parent = self.clean_values(p)
            clean_parent.user = user
            parent = self.find_existing(cls, model_to_dict(clean_parent), user)
            if not parent:
                parent = clean_parent
                parent._state.adding = True
                parent.save()
            for child in children:

                if cls == models.List:
                    exists = self.find_existing(
                        models.ListItem, {"book": book, "book_list": parent}, user
                    )
                if cls == models.Shelf:
                    exists = self.find_existing(
                        models.ShelfBook,
                        {
                            "book": book,
                            "shelf": parent,
                            "shelved_date": child.shelved_date,
                        },
                        user,
                    )

                if not exists:

                    if child.__class__.__name__ == "ListItem":
                        self.create_instance_if_not_exists(
                            models.ListItem,
                            {
                                "book": book,
                                "book_list": parent,
                                "notes": child.notes,
                                "user": user,
                                "order": child.order,
                            },
                        )

                    if child.__class__.__name__ == "ShelfBook":
                        self.create_instance_if_not_exists(
                            models.ShelfBook,
                            {
                                "book": book,
                                "shelf": parent,
                                "shelved_date": child.shelved_date,
                                "user": user,
                            },
                        )

    def create_merged_objects_if_not_exists(self, cls, data, user):
        """Take a serialised JSON string of two connected model instances saved together and
        find or create the instances in the database e.g. Reviews"""

        # NOTE this would probably work for quotes and comments with a bit of tweaking

        deserialized = serializers.deserialize("json", data)
        reviews = []
        statuses = []
        for obj in deserialized:
            if obj.object.__class__.__name__ == "Review":
                reviews.append(obj.object)
            else:
                statuses.append(obj.object)

        if len(reviews) > 0:
            for r in reviews:
                status = next(s for s in statuses if s.id == r.id)
                status.name = r.name
                status.rating = r.rating
                status.user = user

            self.create_instance_if_not_exists(models.Review, self.clean_values(status))
