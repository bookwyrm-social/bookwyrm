"""Export user account to tar.gz file for import into another Bookwyrm instance"""

import logging
import os

from boto3.session import Session as BotoSession
from s3_tar import S3Tar

from django.db.models import FileField, JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.base import ContentFile
from django.core.files.storage import storages

from bookwyrm import settings

from bookwyrm.models import AnnualGoal, ReadThrough, ShelfBook, ListItem
from bookwyrm.models import Review, Comment, Quotation
from bookwyrm.models import Edition
from bookwyrm.models import UserFollows, User, UserBlocks
from bookwyrm.models.job import ParentJob, ParentTask
from bookwyrm.tasks import app, IMPORTS
from bookwyrm.utils.tar import BookwyrmTarFile

logger = logging.getLogger(__name__)


class BookwyrmAwsSession(BotoSession):
    """a boto session that always uses settings.AWS_S3_ENDPOINT_URL"""

    def client(self, *args, **kwargs):
        kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL
        return super().client("s3", *args, **kwargs)


def select_exports_storage():
    """callable to allow for dependency on runtime configuration"""
    return storages["exports"]


class BookwyrmExportJob(ParentJob):
    """entry for a specific request to export a bookwyrm user"""

    export_data = FileField(null=True, storage=select_exports_storage)
    export_json = JSONField(null=True, encoder=DjangoJSONEncoder)

    def start_job(self):
        """schedule the first task"""

        self.set_status("active")
        create_export_json_task.delay(job_id=self.id)


@app.task(queue=IMPORTS, base=ParentTask)
def create_export_json_task(**kwargs):
    """create the JSON data for the export"""

    job = BookwyrmExportJob.objects.get(id=kwargs["job_id"])
    # don't start the job if it was stopped from the UI
    if job.status == "stopped":
        return

    try:
        # generate JSON
        data = export_user(job.user)
        data["settings"] = export_settings(job.user)
        data["goals"] = export_goals(job.user)
        data["books"] = export_books(job.user)
        data["saved_lists"] = export_saved_lists(job.user)
        data["follows"] = export_follows(job.user)
        data["blocks"] = export_blocks(job.user)
        job.export_json = data
        job.save(update_fields=["export_json"])

        # trigger task to create tar file
        create_archive_task.delay(job_id=job.id)

    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            "create_export_json_task for job %s failed with error: %s", job.id, err
        )
        job.set_status("failed")


def archive_file_location(file, directory="") -> str:
    """get the relative location of a file inside the archive"""
    return os.path.join(directory, file.name)


def add_file_to_s3_tar(s3_tar: S3Tar, storage, file, directory=""):
    """
    add file to S3Tar inside directory, keeping any directories under its
    storage location
    """
    s3_tar.add_file(
        os.path.join(storage.location, file.name),
        folder=os.path.dirname(archive_file_location(file, directory=directory)),
    )


@app.task(queue=IMPORTS, base=ParentTask)
def create_archive_task(**kwargs):
    """create the archive containing the JSON file and additional files"""

    job = BookwyrmExportJob.objects.get(id=kwargs["job_id"])

    # don't start the job if it was stopped from the UI
    if job.status == "stopped":
        return

    try:
        export_task_id = str(job.task_id)
        archive_filename = f"{export_task_id}.tar.gz"
        export_json_bytes = DjangoJSONEncoder().encode(job.export_json).encode("utf-8")
        user = job.user
        editions = get_books_for_user(user)

        if settings.USE_S3:
            # Storage for writing temporary files
            exports_storage = storages["exports"]

            # Handle for creating the final archive
            s3_tar = S3Tar(
                exports_storage.bucket_name,
                os.path.join(exports_storage.location, archive_filename),
                session=BookwyrmAwsSession(),
            )

            # Save JSON file to a temporary location
            export_json_tmp_file = os.path.join(export_task_id, "archive.json")
            exports_storage.save(
                export_json_tmp_file,
                ContentFile(export_json_bytes),
            )
            s3_tar.add_file(
                os.path.join(exports_storage.location, export_json_tmp_file)
            )

            # Add images to TAR
            images_storage = storages["default"]

            if user.avatar:
                add_file_to_s3_tar(s3_tar, images_storage, user.avatar)

            for edition in editions:
                if edition.cover:
                    add_file_to_s3_tar(
                        s3_tar, images_storage, edition.cover, directory="images"
                    )

            # Create archive and store file name
            s3_tar.tar()
            job.export_data = archive_filename
            job.save(update_fields=["export_data"])

            # Delete temporary files
            exports_storage.delete(export_json_tmp_file)

        else:
            job.export_data = archive_filename
            with job.export_data.open("wb") as tar_file:
                with BookwyrmTarFile.open(mode="w:gz", fileobj=tar_file) as tar:
                    # save json file
                    tar.write_bytes(export_json_bytes)

                    # Add avatar image if present
                    if user.avatar:
                        tar.add_image(user.avatar)

                    for edition in editions:
                        if edition.cover:
                            tar.add_image(edition.cover, directory="images")
            job.save(update_fields=["export_data"])

        job.complete_job()

    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            "create_archive_task for job %s failed with error: %s", job.id, err
        )
        job.set_status("failed")


def export_user(user: User):
    """export user data"""
    data = user.to_activity()
    if user.avatar:
        data["icon"]["url"] = archive_file_location(user.avatar)
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

    if edition.cover:
        data["edition"]["cover"]["url"] = archive_file_location(
            edition.cover, directory="images"
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
    """
    Get all the books and editions related to a user.
    We use union() instead of Q objects because it creates
    multiple simple queries instead of a complex DB query
    that can time out.
    """

    shelf_eds = Edition.objects.select_related("parent_work").filter(shelves__user=user)
    rt_eds = Edition.objects.select_related("parent_work").filter(
        readthrough__user=user
    )
    review_eds = Edition.objects.select_related("parent_work").filter(review__user=user)
    list_eds = Edition.objects.select_related("parent_work").filter(list__user=user)
    comment_eds = Edition.objects.select_related("parent_work").filter(
        comment__user=user
    )
    quote_eds = Edition.objects.select_related("parent_work").filter(
        quotation__user=user
    )

    editions = shelf_eds.union(rt_eds, review_eds, list_eds, comment_eds, quote_eds)

    return editions
