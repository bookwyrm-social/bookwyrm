"""Import a user from another Bookwyrm instance"""

import json
import logging

from django.db.models import FileField, JSONField, CharField
from django.utils import timezone
from django.utils.html import strip_tags
from django.contrib.postgres.fields import ArrayField as DjangoArrayField

from bookwyrm import activitypub
from bookwyrm import models
from bookwyrm.tasks import app, IMPORTS
from bookwyrm.models.job import ParentJob, ParentTask, SubTask
from bookwyrm.utils.tar import BookwyrmTarFile

logger = logging.getLogger(__name__)


class BookwyrmImportJob(ParentJob):
    """entry for a specific request for importing a bookwyrm user backup"""

    archive_file = FileField(null=True, blank=True)
    import_data = JSONField(null=True)
    required = DjangoArrayField(CharField(max_length=50, blank=True), blank=True)

    def start_job(self):
        """Start the job"""
        start_import_task.delay(job_id=self.id, no_children=True)


@app.task(queue=IMPORTS, base=ParentTask)
def start_import_task(**kwargs):
    """trigger the child import tasks for each user data"""
    job = BookwyrmImportJob.objects.get(id=kwargs["job_id"])
    archive_file = job.archive_file

    # don't start the job if it was stopped from the UI
    if job.complete:
        return

    try:
        archive_file.open("rb")
        with BookwyrmTarFile.open(mode="r:gz", fileobj=archive_file) as tar:
            job.import_data = json.loads(tar.read("archive.json").decode("utf-8"))

            if "include_user_profile" in job.required:
                update_user_profile(job.user, tar, job.import_data)
            if "include_user_settings" in job.required:
                update_user_settings(job.user, job.import_data)
            if "include_goals" in job.required:
                update_goals(job.user, job.import_data.get("goals"))
            if "include_saved_lists" in job.required:
                upsert_saved_lists(job.user, job.import_data.get("saved_lists"))
            if "include_follows" in job.required:
                upsert_follows(job.user, job.import_data.get("follows"))
            if "include_blocks" in job.required:
                upsert_user_blocks(job.user, job.import_data.get("blocks"))

            process_books(job, tar)

            job.set_status("complete")
        archive_file.close()

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("User Import Job %s Failed with error: %s", job.id, err)
        job.set_status("failed")


def process_books(job, tar):
    """
    Process user import data related to books
    We always import the books even if not assigning
    them to shelves, lists etc
    """

    books = job.import_data.get("books")

    for data in books:
        book = get_or_create_edition(data, tar)

        if "include_shelves" in job.required:
            upsert_shelves(book, job.user, data)

        if "include_readthroughs" in job.required:
            upsert_readthroughs(data.get("readthroughs"), job.user, book.id)

        if "include_comments" in job.required:
            upsert_statuses(
                job.user, models.Comment, data.get("comments"), book.remote_id
            )
        if "include_quotations" in job.required:
            upsert_statuses(
                job.user, models.Quotation, data.get("quotations"), book.remote_id
            )

        if "include_reviews" in job.required:
            upsert_statuses(
                job.user, models.Review, data.get("reviews"), book.remote_id
            )

        if "include_lists" in job.required:
            upsert_lists(job.user, data.get("lists"), book.id)


def get_or_create_edition(book_data, tar):
    """Take a JSON string of work and edition data,
    find or create the edition and work in the database and
    return an edition instance"""

    edition = book_data.get("edition")
    existing = models.Edition.find_existing(edition)
    if existing:
        return existing

    # make sure we have the authors in the local DB
    # replace the old author ids in the edition JSON
    edition["authors"] = []
    for author in book_data.get("authors"):
        parsed_author = activitypub.parse(author)
        instance = parsed_author.to_model(
            model=models.Author, save=True, overwrite=True
        )

        edition["authors"].append(instance.remote_id)

    # we will add the cover later from the tar
    # don't try to load it from the old server
    cover = edition.get("cover", {})
    cover_path = cover.get("url", None)
    edition["cover"] = {}

    # first we need the parent work to exist
    work = book_data.get("work")
    work["editions"] = []
    parsed_work = activitypub.parse(work)
    work_instance = parsed_work.to_model(model=models.Work, save=True, overwrite=True)

    # now we have a work we can add it to the edition
    # and create the edition model instance
    edition["work"] = work_instance.remote_id
    parsed_edition = activitypub.parse(edition)
    book = parsed_edition.to_model(model=models.Edition, save=True, overwrite=True)

    # set the cover image from the tar
    if cover_path:
        tar.write_image_to_file(cover_path, book.cover)

    return book


def upsert_readthroughs(data, user, book_id):
    """Take a JSON string of readthroughs and
    find or create the instances in the database"""

    for read_through in data:

        obj = {}
        keys = [
            "progress_mode",
            "start_date",
            "finish_date",
            "stopped_date",
            "is_active",
        ]
        for key in keys:
            obj[key] = read_through[key]
        obj["user_id"] = user.id
        obj["book_id"] = book_id

        existing = models.ReadThrough.objects.filter(**obj).first()
        if not existing:
            models.ReadThrough.objects.create(**obj)


def upsert_statuses(user, cls, data, book_remote_id):
    """Take a JSON string of a status and
    find or create the instances in the database"""

    for status in data:
        if is_alias(
            user, status["attributedTo"]
        ):  # don't let l33t hax0rs steal other people's posts
            # update ids and remove replies
            status["attributedTo"] = user.remote_id
            status["to"] = update_followers_address(user, status["to"])
            status["cc"] = update_followers_address(user, status["cc"])
            status[
                "replies"
            ] = (
                {}
            )  # this parses incorrectly but we can't set it without knowing the new id
            status["inReplyToBook"] = book_remote_id
            parsed = activitypub.parse(status)
            if not status_already_exists(
                user, parsed
            ):  # don't duplicate posts on multiple import

                instance = parsed.to_model(model=cls, save=True, overwrite=True)

                for val in [
                    "progress",
                    "progress_mode",
                    "position",
                    "endposition",
                    "position_mode",
                ]:
                    if status.get(val):
                        instance.val = status[val]

                instance.remote_id = instance.get_remote_id()  # update the remote_id
                instance.save()  # save and broadcast

        else:
            logger.info("User does not have permission to import statuses")


def upsert_lists(user, lists, book_id):
    """Take a list of objects each containing
    a list and list item as AP objects

    Because we are creating new IDs we can't assume the id
    will exist or be accurate, so we only use to_model for
    adding new items after checking whether they exist  .

    """

    book = models.Edition.objects.get(id=book_id)

    for blist in lists:
        booklist = models.List.objects.filter(name=blist["name"], user=user).first()
        if not booklist:

            blist["owner"] = user.remote_id
            parsed = activitypub.parse(blist)
            booklist = parsed.to_model(model=models.List, save=True, overwrite=True)

            booklist.privacy = blist["privacy"]
            booklist.save()

        item = models.ListItem.objects.filter(book=book, book_list=booklist).exists()
        if not item:
            count = booklist.books.count()
            models.ListItem.objects.create(
                book=book,
                book_list=booklist,
                user=user,
                notes=blist["list_item"]["notes"],
                approved=blist["list_item"]["approved"],
                order=count + 1,
            )


def upsert_shelves(book, user, book_data):
    """Take shelf JSON objects and create
    DB entries if they don't already exist"""

    shelves = book_data["shelves"]
    for shelf in shelves:

        book_shelf = models.Shelf.objects.filter(name=shelf["name"], user=user).first()

        if not book_shelf:
            book_shelf = models.Shelf.objects.create(name=shelf["name"], user=user)

        # add the book as a ShelfBook if needed
        if not models.ShelfBook.objects.filter(
            book=book, shelf=book_shelf, user=user
        ).exists():
            models.ShelfBook.objects.create(
                book=book, shelf=book_shelf, user=user, shelved_date=timezone.now()
            )


def update_user_profile(user, tar, data):
    """update the user's profile from import data"""
    name = data.get("name", None)
    username = data.get("preferredUsername")
    user.name = name if name else username
    user.summary = strip_tags(data.get("summary", None))
    user.save(update_fields=["name", "summary"])
    if data["icon"].get("url"):
        avatar_filename = next(filter(lambda n: n.startswith("avatar"), tar.getnames()))
        tar.write_image_to_file(avatar_filename, user.avatar)


def update_user_settings(user, data):
    """update the user's settings from import data"""

    update_fields = ["manually_approves_followers", "hide_follows", "discoverable"]

    ap_fields = [
        ("manuallyApprovesFollowers", "manually_approves_followers"),
        ("hideFollows", "hide_follows"),
        ("discoverable", "discoverable"),
    ]

    for (ap_field, bw_field) in ap_fields:
        setattr(user, bw_field, data[ap_field])

    bw_fields = [
        "show_goal",
        "show_suggested_users",
        "default_post_privacy",
        "preferred_timezone",
    ]

    for field in bw_fields:
        update_fields.append(field)
        setattr(user, field, data["settings"][field])

    user.save(update_fields=update_fields)


@app.task(queue=IMPORTS, base=SubTask)
def update_user_settings_task(job_id):
    """wrapper task for user's settings import"""
    parent_job = BookwyrmImportJob.objects.get(id=job_id)

    return update_user_settings(parent_job.user, parent_job.import_data.get("user"))


def update_goals(user, data):
    """update the user's goals from import data"""

    for goal in data:
        # edit the existing goal if there is one
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


@app.task(queue=IMPORTS, base=SubTask)
def update_goals_task(job_id):
    """wrapper task for user's goals import"""
    parent_job = BookwyrmImportJob.objects.get(id=job_id)

    return update_goals(parent_job.user, parent_job.import_data.get("goals"))


def upsert_saved_lists(user, values):
    """Take a list of remote ids and add as saved lists"""

    for remote_id in values:
        book_list = activitypub.resolve_remote_id(remote_id, models.List)
        if book_list:
            user.saved_lists.add(book_list)


@app.task(queue=IMPORTS, base=SubTask)
def upsert_saved_lists_task(job_id):
    """wrapper task for user's saved lists import"""
    parent_job = BookwyrmImportJob.objects.get(id=job_id)

    return upsert_saved_lists(
        parent_job.user, parent_job.import_data.get("saved_lists")
    )


def upsert_follows(user, values):
    """Take a list of remote ids and add as follows"""

    for remote_id in values:
        followee = activitypub.resolve_remote_id(remote_id, models.User)
        if followee:
            (follow_request, created,) = models.UserFollowRequest.objects.get_or_create(
                user_subject=user,
                user_object=followee,
            )

            if not created:
                # this request probably failed to connect with the remote
                # and should save to trigger a re-broadcast
                follow_request.save()


@app.task(queue=IMPORTS, base=SubTask)
def upsert_follows_task(job_id):
    """wrapper task for user's follows import"""
    parent_job = BookwyrmImportJob.objects.get(id=job_id)

    return upsert_follows(parent_job.user, parent_job.import_data.get("follows"))


def upsert_user_blocks(user, user_ids):
    """block users"""

    for user_id in user_ids:
        user_object = activitypub.resolve_remote_id(user_id, models.User)
        if user_object:
            exists = models.UserBlocks.objects.filter(
                user_subject=user, user_object=user_object
            ).exists()
            if not exists:
                models.UserBlocks.objects.create(
                    user_subject=user, user_object=user_object
                )
                # remove the blocked users's lists from the groups
                models.List.remove_from_group(user, user_object)
                # remove the blocked user from all blocker's owned groups
                models.GroupMember.remove(user, user_object)


@app.task(queue=IMPORTS, base=SubTask)
def upsert_user_blocks_task(job_id):
    """wrapper task for user's blocks import"""
    parent_job = BookwyrmImportJob.objects.get(id=job_id)

    return upsert_user_blocks(
        parent_job.user, parent_job.import_data.get("blocked_users")
    )


def update_followers_address(user, field):
    """statuses to or cc followers need to have the followers
    address updated to the new local user"""

    for i, audience in enumerate(field):
        if audience.rsplit("/")[-1] == "followers":
            field[i] = user.followers_url

    return field


def is_alias(user, remote_id):
    """check that the user is listed as movedTo or also_known_as
    in the remote user's profile"""

    remote_user = activitypub.resolve_remote_id(
        remote_id=remote_id, model=models.User, save=False
    )

    if remote_user:

        if remote_user.moved_to:
            return user.remote_id == remote_user.moved_to

        if remote_user.also_known_as:
            return user in remote_user.also_known_as.all()

    return False


def status_already_exists(user, status):
    """check whether this status has already been published
    by this user. We can't rely on to_model() because it
    only matches on remote_id, which we have to change
    *after* saving because it needs the primary key (id)"""

    return models.Status.objects.filter(
        user=user, content=status.content, published_date=status.published
    ).exists()
