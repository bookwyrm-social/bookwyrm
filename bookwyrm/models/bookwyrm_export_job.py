"""Export user account to tar.gz file for import into another Bookwyrm instance"""

import dataclasses
import logging
from uuid import uuid4

from django.db.models import FileField
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.base import ContentFile

from bookwyrm.models import AnnualGoal, ReadThrough, ShelfBook, List, ListItem
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

    # User as AP object
    exported_user = user.to_activity()
    # I don't love this but it prevents a JSON encoding error
    # when there is no user image
    if exported_user.get("icon") in (None, dataclasses.MISSING):
        exported_user["icon"] = {}
    else:
        # change the URL to be relative to the JSON file
        file_type = exported_user["icon"]["url"].rsplit(".", maxsplit=1)[-1]
        filename = f"avatar.{file_type}"
        exported_user["icon"]["url"] = filename

    # Additional settings - can't be serialized as AP
    vals = [
        "show_goal",
        "preferred_timezone",
        "default_post_privacy",
        "show_suggested_users",
    ]
    exported_user["settings"] = {}
    for k in vals:
        exported_user["settings"][k] = getattr(user, k)

    # Reading goals - can't be serialized as AP
    reading_goals = AnnualGoal.objects.filter(user=user).distinct()
    exported_user["goals"] = []
    for goal in reading_goals:
        exported_user["goals"].append(
            {"goal": goal.goal, "year": goal.year, "privacy": goal.privacy}
        )

    # Reading history - can't be serialized as AP
    readthroughs = ReadThrough.objects.filter(user=user).distinct().values()
    readthroughs = list(readthroughs)

    # Books
    editions = get_books_for_user(user)
    exported_user["books"] = []

    for edition in editions:
        book = {}
        book["work"] = edition.parent_work.to_activity()
        book["edition"] = edition.to_activity()

        if book["edition"].get("cover"):
            # change the URL to be relative to the JSON file
            filename = book["edition"]["cover"]["url"].rsplit("/", maxsplit=1)[-1]
            book["edition"]["cover"]["url"] = f"covers/{filename}"

        # authors
        book["authors"] = []
        for author in edition.authors.all():
            book["authors"].append(author.to_activity())

        # Shelves this book is on
        # Every ShelfItem is this book so we don't other serializing
        book["shelves"] = []
        shelf_books = (
            ShelfBook.objects.select_related("shelf")
            .filter(user=user, book=edition)
            .distinct()
        )

        for shelfbook in shelf_books:
            book["shelves"].append(shelfbook.shelf.to_activity())

        # Lists and ListItems
        # ListItems include "notes" and "approved" so we need them
        # even though we know it's this book
        book["lists"] = []
        list_items = ListItem.objects.filter(book=edition, user=user).distinct()

        for item in list_items:
            list_info = item.book_list.to_activity()
            list_info[
                "privacy"
            ] = item.book_list.privacy  # this isn't serialized so we add it
            list_info["list_item"] = item.to_activity()
            book["lists"].append(list_info)

        # Statuses
        # Can't use select_subclasses here because
        # we need to filter on the "book" value,
        # which is not available on an ordinary Status
        for status in ["comments", "quotations", "reviews"]:
            book[status] = []

        comments = Comment.objects.filter(user=user, book=edition).all()
        for status in comments:
            obj = status.to_activity()
            obj["progress"] = status.progress
            obj["progress_mode"] = status.progress_mode
            book["comments"].append(obj)

        quotes = Quotation.objects.filter(user=user, book=edition).all()
        for status in quotes:
            obj = status.to_activity()
            obj["position"] = status.position
            obj["endposition"] = status.endposition
            obj["position_mode"] = status.position_mode
            book["quotations"].append(obj)

        reviews = Review.objects.filter(user=user, book=edition).all()
        for status in reviews:
            obj = status.to_activity()
            book["reviews"].append(obj)

        # readthroughs can't be serialized to activity
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

    editions = (
        Edition.objects.select_related("parent_work")
        .filter(
            Q(shelves__user=user)
            | Q(readthrough__user=user)
            | Q(review__user=user)
            | Q(list__user=user)
            | Q(comment__user=user)
            | Q(quotation__user=user)
        )
        .distinct()
    )

    return editions
