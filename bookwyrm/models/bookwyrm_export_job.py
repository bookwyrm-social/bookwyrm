"""Export user account to tar.gz file for import into another Bookwyrm instance"""

import logging
from urllib.parse import urlparse, unquote

from boto3.session import Session as BotoSession
from s3_tar import S3Tar
from storages.backends.s3boto3 import S3Boto3Storage

from django.db.models import BooleanField, FileField, JSONField
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.base import ContentFile
from django.utils.module_loading import import_string

from bookwyrm import settings

from bookwyrm.models import AnnualGoal, ReadThrough, ShelfBook, ListItem
from bookwyrm.models import Review, Comment, Quotation
from bookwyrm.models import Edition
from bookwyrm.models import UserFollows, User, UserBlocks
from bookwyrm.models.job import ParentJob
from bookwyrm.tasks import app, IMPORTS
from bookwyrm.utils.tar import BookwyrmTarFile

logger = logging.getLogger(__name__)


class BookwyrmAwsSession(BotoSession):
    """a boto session that always uses settings.AWS_S3_ENDPOINT_URL"""

    def client(self, *args, **kwargs):  # pylint: disable=arguments-differ
        kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL
        return super().client("s3", *args, **kwargs)


def select_exports_storage():
    """callable to allow for dependency on runtime configuration"""
    cls = import_string(settings.EXPORTS_STORAGE)
    return cls()


class BookwyrmExportJob(ParentJob):
    """entry for a specific request to export a bookwyrm user"""

    export_data = FileField(null=True, storage=select_exports_storage)
    export_json = JSONField(null=True, encoder=DjangoJSONEncoder)
    json_completed = BooleanField(default=False)

    def start_job(self):
        """schedule the first task"""

        task = create_export_json_task.delay(job_id=self.id)
        self.task_id = task.id
        self.save(update_fields=["task_id"])


def url2relativepath(url: str) -> str:
    """turn an absolute URL into a relative filesystem path"""
    parsed = urlparse(url)
    return unquote(parsed.path[1:])


@app.task(queue=IMPORTS)
def create_export_json_task(job_id):
    """create the JSON data for the export"""

    job = BookwyrmExportJob.objects.get(id=job_id)

    # don't start the job if it was stopped from the UI
    if job.complete:
        return

    try:
        job.set_status("active")

        # generate JSON structure
        job.export_json = export_json(job.user)
        job.save(update_fields=["export_json"])

        # create archive in separate task
        create_archive_task.delay(job_id=job.id)
    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            "create_export_json_task for %s failed with error: %s", job, err
        )
        job.set_status("failed")


@app.task(queue=IMPORTS)
def create_archive_task(job_id):
    """create the archive containing the JSON file and additional files"""

    job = BookwyrmExportJob.objects.get(id=job_id)

    # don't start the job if it was stopped from the UI
    if job.complete:
        return

    try:
        export_task_id = job.task_id
        export_json_bytes = DjangoJSONEncoder().encode(job.export_json).encode("utf-8")

        user = job.user
        editions = get_books_for_user(user)

        if settings.USE_S3:
            # Connection for writing temporary files
            storage = S3Boto3Storage()

            # Handle for creating the final archive
            s3_archive_path = f"exports/{export_task_id}.tar.gz"
            s3_tar = S3Tar(
                settings.AWS_STORAGE_BUCKET_NAME,
                s3_archive_path,
                session=BookwyrmAwsSession(),
            )

            # Save JSON file to a temporary location
            export_json_tmp_file = f"exports/{export_task_id}/archive.json"
            S3Boto3Storage.save(
                storage,
                export_json_tmp_file,
                ContentFile(export_json_bytes),
            )
            s3_tar.add_file(export_json_tmp_file)

            # Add avatar image if present
            if user.avatar:
                s3_tar.add_file(f"images/{user.avatar.name}")

            for edition in editions:
                if edition.cover:
                    s3_tar.add_file(f"images/{edition.cover.name}")

            # Create archive and store file name
            s3_tar.tar()
            job.export_data = s3_archive_path
            job.save(update_fields=["export_data"])

            # Delete temporary files
            S3Boto3Storage.delete(storage, export_json_tmp_file)

        else:
            job.export_data = f"{export_task_id}.tar.gz"
            with job.export_data.open("wb") as tar_file:
                with BookwyrmTarFile.open(mode="w:gz", fileobj=tar_file) as tar:
                    # save json file
                    tar.write_bytes(export_json_bytes)

                    # Add avatar image if present
                    if user.avatar:
                        tar.add_image(user.avatar, directory="images/")

                    for edition in editions:
                        if edition.cover:
                            tar.add_image(edition.cover, directory="images/")
            job.save(update_fields=["export_data"])

        job.set_status("completed")

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("create_archive_task for %s failed with error: %s", job, err)
        job.set_status("failed")


def export_json(user: User):
    """create export JSON"""
    data = export_user(user)  # in the root of the JSON structure
    data["settings"] = export_settings(user)
    data["goals"] = export_goals(user)
    data["books"] = export_books(user)
    data["saved_lists"] = export_saved_lists(user)
    data["follows"] = export_follows(user)
    data["blocks"] = export_blocks(user)
    return data


def export_user(user: User):
    """export user data"""
    data = user.to_activity()
    if data.get("icon", False):
        data["icon"]["url"] = url2relativepath(data["icon"]["url"])
    else:
        data["icon"] = {}
    return data


def export_settings(user: User):
    """Additional settings - can't be serialized as AP"""
    vals = [
        "show_goal",
        "preferred_timezone",
        "default_post_privacy",
        "show_suggested_users",
    ]
    return {k: getattr(user, k) for k in vals}


def export_saved_lists(user: User):
    """add user saved lists to export JSON"""
    return [l.remote_id for l in user.saved_lists.all()]


def export_follows(user: User):
    """add user follows to export JSON"""
    follows = UserFollows.objects.filter(user_subject=user).distinct()
    following = User.objects.filter(userfollows_user_object__in=follows).distinct()
    return [f.remote_id for f in following]


def export_blocks(user: User):
    """add user blocks to export JSON"""
    blocks = UserBlocks.objects.filter(user_subject=user).distinct()
    blocking = User.objects.filter(userblocks_user_object__in=blocks).distinct()
    return [b.remote_id for b in blocking]


def export_goals(user: User):
    """add user reading goals to export JSON"""
    reading_goals = AnnualGoal.objects.filter(user=user).distinct()
    return [
        {"goal": goal.goal, "year": goal.year, "privacy": goal.privacy}
        for goal in reading_goals
    ]


def export_books(user: User):
    """add books to export JSON"""
    editions = get_books_for_user(user)
    return [export_book(user, edition) for edition in editions]


def export_book(user: User, edition: Edition):
    """add book to export JSON"""
    data = {}
    data["work"] = edition.parent_work.to_activity()
    data["edition"] = edition.to_activity()

    if data["edition"].get("cover", False):
        data["edition"]["cover"]["url"] = url2relativepath(
            data["edition"]["cover"]["url"]
        )

    # authors
    data["authors"] = [author.to_activity() for author in edition.authors.all()]

    # Shelves this book is on
    # Every ShelfItem is this book so we don't other serializing
    shelf_books = (
        ShelfBook.objects.select_related("shelf")
        .filter(user=user, book=edition)
        .distinct()
    )
    data["shelves"] = [shelfbook.shelf.to_activity() for shelfbook in shelf_books]

    # Lists and ListItems
    # ListItems include "notes" and "approved" so we need them
    # even though we know it's this book
    list_items = ListItem.objects.filter(book=edition, user=user).distinct()

    data["lists"] = []
    for item in list_items:
        list_info = item.book_list.to_activity()
        list_info[
            "privacy"
        ] = item.book_list.privacy  # this isn't serialized so we add it
        list_info["list_item"] = item.to_activity()
        data["lists"].append(list_info)

    # Statuses
    # Can't use select_subclasses here because
    # we need to filter on the "book" value,
    # which is not available on an ordinary Status
    for status in ["comments", "quotations", "reviews"]:
        data[status] = []

    comments = Comment.objects.filter(user=user, book=edition).all()
    for status in comments:
        obj = status.to_activity()
        obj["progress"] = status.progress
        obj["progress_mode"] = status.progress_mode
        data["comments"].append(obj)

    quotes = Quotation.objects.filter(user=user, book=edition).all()
    for status in quotes:
        obj = status.to_activity()
        obj["position"] = status.position
        obj["endposition"] = status.endposition
        obj["position_mode"] = status.position_mode
        data["quotations"].append(obj)

    reviews = Review.objects.filter(user=user, book=edition).all()
    data["reviews"] = [status.to_activity() for status in reviews]

    # readthroughs can't be serialized to activity
    book_readthroughs = (
        ReadThrough.objects.filter(user=user, book=edition).distinct().values()
    )
    data["readthroughs"] = list(book_readthroughs)
    return data


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
