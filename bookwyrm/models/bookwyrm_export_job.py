"""Export user account to tar.gz file for import into another Bookwyrm instance"""

import dataclasses
import logging
from uuid import uuid4

from django.db.models import FileField
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.base import ContentFile

from bookwyrm.models import AnnualGoal, ReadThrough, ShelfBook, Shelf, List, ListItem
from bookwyrm.models import Review, Comment, Quotation
from bookwyrm.models import Edition
from bookwyrm.models import UserFollows, User, UserBlocks
from bookwyrm.models.job import ParentJob, ParentTask
from bookwyrm.tasks import app, IMPORTS
from bookwyrm.utils.tar import BookwyrmTarFile

logger = logging.getLogger(__name__)


class BookwyrmExportJob(ParentJob):
    """entry for a specific request to export a bookwyrm user"""

    export_data = FileField(null=True)

    def start_job(self):
        """Start the job"""
        start_export_task.delay(job_id=self.id, no_children=True)

        return self


@app.task(queue=IMPORTS, base=ParentTask)
def start_export_task(**kwargs):
    """trigger the child tasks for each row"""
    job = BookwyrmExportJob.objects.get(id=kwargs["job_id"])

    # don't start the job if it was stopped from the UI
    if job.complete:
        return
    try:
        # This is where ChildJobs get made
        job.export_data = ContentFile(b"", str(uuid4()))
        json_data = json_export(job.user)
        tar_export(json_data, job.user, job.export_data)
        job.save(update_fields=["export_data"])
    except Exception as err:  # pylint: disable=broad-except
        logger.exception("User Export Job %s Failed with error: %s", job.id, err)
        job.set_status("failed")

    job.set_status("complete")


def tar_export(json_data: str, user, file):
    """wrap the export information in a tar file"""
    file.open("wb")
    with BookwyrmTarFile.open(mode="w:gz", fileobj=file) as tar:
        tar.write_bytes(json_data.encode("utf-8"))

        # Add avatar image if present
        if getattr(user, "avatar", False):
            tar.add_image(user.avatar, filename="avatar")

        editions = get_books_for_user(user)
        for book in editions:
            if getattr(book, "cover", False):
                tar.add_image(book.cover)

    file.close()


def json_export(
    user,
):  # pylint: disable=too-many-locals, too-many-statements, too-many-branches
    """Generate an export for a user"""

    exported_user = {}

    # User as AP object
    exported_user = user.to_activity()
    # I don't love this but it prevents a JSON encoding error
    # when there is no user image
    if isinstance(exported_user["icon"], dataclasses._MISSING_TYPE):
        exported_user["icon"] = {}
    else:
        # change the URL to be relative to the JSON file
        file_type = exported_user["icon"]["url"].rsplit(".", maxsplit=1)[-1]
        filename = f"avatar.{file_type}"
        exported_user["icon"]["url"] = filename

    # Additional settings
    # can't be serialized as AP
    vals = [
        "show_goal",
        "preferred_timezone",
        "default_post_privacy",
        "show_suggested_users",
    ]
    exported_user["settings"] = {}
    for k in vals:
        exported_user["settings"][k] = getattr(user, k)

    # Reading goals
    # can't be serialized as AP
    reading_goals = AnnualGoal.objects.filter(user=user).distinct()
    exported_user["goals"] = []
    for goal in reading_goals:
        exported_user["goals"].append(
            {"goal": goal.goal, "year": goal.year, "privacy": goal.privacy}
        )

    # Reading history
    # can't be serialized as AP
    readthroughs = ReadThrough.objects.filter(user=user).distinct().values()
    readthroughs = list(readthroughs)

    # Books
    editions = get_books_for_user(user)
    exported_user["books"] = []
    for edition in editions:
        book = {}
        book["edition"] = edition.to_activity()

        # authors
        book["authors"] = []
        for author in edition.authors.all():
            obj = author.to_activity()
            book["authors"].append(obj)

        # Shelves this book is on
        # All we want is the shelf identifier and name
        # Every ShelfItem is this book so there's no point
        # serialising to_activity()
        # can be serialized as AP but can't use to_model on import
        book["shelves"] = []
        shelf_books = ShelfBook.objects.filter(book=edition).distinct()
        user_shelves = Shelf.objects.filter(id__in=shelf_books)

        for shelf in user_shelves:
            obj = {
                "identifier": shelf.identifier,
                "name": shelf.name,
                "description": shelf.description,
                "editable": shelf.editable,
                "privacy": shelf.privacy,
            }
            book["shelves"].append(obj)

        # Lists and ListItems
        # ListItems include "notes" and "approved" so we need them
        # even though we know it's this book
        book["lists"] = []
        user_lists = List.objects.filter(user=user).all()

        for booklist in user_lists:
            obj = {"list_items": []}
            obj["list_info"] = booklist.to_activity()
            obj["list_info"]["privacy"] = booklist.privacy
            list_items = ListItem.objects.filter(book_list=booklist).distinct()
            for item in list_items:
                obj["list_items"].append(item.to_activity())

            book["lists"].append(obj)

        # Statuses
        # Can't use select_subclasses here because
        # we need to filter on the "book" value,
        # which is not available on an ordinary Status
        for status in ["comments", "quotations", "reviews"]:
            book[status] = []

        comments = Comment.objects.filter(user=user, book=edition).all()
        for status in comments:
            book["comments"].append(status.to_activity())

        quotes = Quotation.objects.filter(user=user, book=edition).all()
        for status in quotes:
            book["quotations"].append(status.to_activity())

        reviews = Review.objects.filter(user=user, book=edition).all()
        for status in reviews:
            book["reviews"].append(status.to_activity())

        # readthroughs can't be serialized to activity
        # so we use values()
        book_readthroughs = (
            ReadThrough.objects.filter(user=user, book=edition).distinct().values()
        )
        book["readthroughs"] = list(book_readthroughs)

        # append everything
        exported_user["books"].append(book)

    # saved book lists - just the remote id
    saved_lists = List.objects.filter(id__in=user.saved_lists.all()).distinct()
    exported_user["saved_lists"] = [l.remote_id for l in saved_lists]

    # follows - just the remote id
    follows = UserFollows.objects.filter(user_subject=user).distinct()
    following = User.objects.filter(userfollows_user_object__in=follows).distinct()
    exported_user["follows"] = [f.remote_id for f in following]

    # blocks - just the remote id
    blocks = UserBlocks.objects.filter(user_subject=user).distinct()
    blocking = User.objects.filter(userblocks_user_object__in=blocks).distinct()

    exported_user["blocks"] = [b.remote_id for b in blocking]

    return DjangoJSONEncoder().encode(exported_user)


def get_books_for_user(user):
    """Get all the books and editions related to a user"""

    editions = Edition.objects.filter(
        Q(shelves__user=user)
        | Q(readthrough__user=user)
        | Q(review__user=user)
        | Q(list__user=user)
        | Q(comment__user=user)
        | Q(quotation__user=user)
    ).distinct()

    return editions
