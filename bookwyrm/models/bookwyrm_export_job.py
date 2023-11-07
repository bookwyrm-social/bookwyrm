"""Export user account to tar.gz file for import into another Bookwyrm instance"""

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
from bookwyrm.settings import DOMAIN
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


def json_export(user):  # pylint: disable=too-many-locals, too-many-statements
    """Generate an export for a user"""
    # user
    exported_user = {}
    vals = [
        "username",
        "name",
        "summary",
        "manually_approves_followers",
        "hide_follows",
        "show_goal",
        "show_suggested_users",
        "discoverable",
        "preferred_timezone",
        "default_post_privacy",
    ]
    for k in vals:
        exported_user[k] = getattr(user, k)

    if getattr(user, "avatar", False):
        exported_user["avatar"] = f'https://{DOMAIN}{getattr(user, "avatar").url}'

    # reading goals
    reading_goals = AnnualGoal.objects.filter(user=user).distinct()
    goals_list = []
    # TODO: either error checking should be more sophisticated
    # or maybe we don't need this try/except
    try:
        for goal in reading_goals:
            goals_list.append(
                {"goal": goal.goal, "year": goal.year, "privacy": goal.privacy}
            )
    except Exception:  # pylint: disable=broad-except
        pass

    try:
        readthroughs = ReadThrough.objects.filter(user=user).distinct().values()
        readthroughs = list(readthroughs)
    except Exception:  # pylint: disable=broad-except
        readthroughs = []

    # books
    editions = get_books_for_user(user)
    final_books = []

    # editions
    for edition in editions:
        book = {}
        book[
            "edition"
        ] = edition.to_activity()  # <== BUG Link field class is unknown here.

        # authors
        book["authors"] = []
        for author in edition.authors.all():
            obj = author.to_activity()
            book["authors"].append(obj)

        # Shelves and shelfbooks
        book["shelves"] = []
        user_shelves = Shelf.objects.filter(user=user).all()

        for shelf in user_shelves:
            obj = {"shelf_books": []}
            obj["shelf_info"] = shelf.to_activity()
            shelf_books = ShelfBook.objects.filter(book=edition, shelf=shelf).distinct()

            for shelfbook in shelf_books:
                obj["shelf_books"].append(shelfbook.to_activity())

            book["shelves"].append(obj)

        # List and ListItem
        book["lists"] = []
        user_lists = List.objects.filter(user=user).all()

        for booklist in user_lists:
            obj = {"list_items": []}
            obj["list_info"] = booklist.to_activity()
            list_items = ListItem.objects.filter(book_list=booklist).distinct()
            for item in list_items:
                obj["list_items"].append(item.to_activity())

            book["lists"].append(obj)

        # Statuses
        # Can't use select_subclasses here because
        # we need to filter on the "book" value,
        # which is not available on an ordinary Status
        for x in ["comments", "quotations", "reviews"]:
            book[x] = []

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
        book_readthroughs = (
            ReadThrough.objects.filter(user=user, book=edition).distinct().values()
        )
        book["readthroughs"] = list(book_readthroughs)

        # append everything
        final_books.append(book)

    logger.info(final_books)

    # saved book lists
    saved_lists = List.objects.filter(id__in=user.saved_lists.all()).distinct()
    saved_lists = [l.remote_id for l in saved_lists]

    # follows
    follows = UserFollows.objects.filter(user_subject=user).distinct()
    following = User.objects.filter(userfollows_user_object__in=follows).distinct()
    follows = [f.remote_id for f in following]

    # blocks
    blocks = UserBlocks.objects.filter(user_subject=user).distinct()
    blocking = User.objects.filter(userblocks_user_object__in=blocks).distinct()

    blocks = [b.remote_id for b in blocking]

    data = {
        "user": exported_user,
        "goals": goals_list,
        "books": final_books,
        "saved_lists": saved_lists,
        "follows": follows,
        "blocked_users": blocks,
    }

    return DjangoJSONEncoder().encode(data)


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
