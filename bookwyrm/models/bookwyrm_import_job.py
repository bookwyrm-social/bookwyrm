from functools import reduce
import json
import logging
import operator

from django.db.models import FileField, JSONField, CharField
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.contrib.postgres.fields import ArrayField as DjangoArrayField

from bookwyrm import activitypub
from bookwyrm import models
from bookwyrm.tasks import app, IMPORTS
from bookwyrm.models.job import (
    ParentJob,
    ParentTask,
    ChildJob,
    SubTask,
    create_child_job,
)
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
                update_user_profile(job.user, tar, job.import_data.get("user"))
            if "include_user_settings" in job.required:
                update_user_settings(job.user, job.import_data.get("user"))
            if "include_goals" in job.required:
                update_goals(job.user, job.import_data.get("goals"))
            if "include_saved_lists" in job.required:
                upsert_saved_lists(job.user, job.import_data.get("saved_lists"))
            if "include_follows" in job.required:
                upsert_follows(job.user, job.import_data.get("follows"))
            if "include_blocks" in job.required:
                upsert_user_blocks(job.user, job.import_data.get("blocked_users"))

            process_books(job, tar)

            job.set_status("complete") # set here to trigger notifications
            job.save()
        archive_file.close()

    except Exception as err:  # pylint: disable=broad-except
        logger.exception("User Import Job %s Failed with error: %s", job.id, err)
        job.set_status("failed")


def process_books(job, tar):
    """process user import data related to books"""

    # create the books. We need to merge Book and Edition instances
    # and also check whether these books already exist in the DB
    books = job.import_data.get("books")

    for data in books:
        book = get_or_create_edition(data, tar)

        if "include_shelves" in job.required:
            upsert_shelves(book, job.user, data)

        if "include_readthroughs" in job.required:
            upsert_readthroughs(data.get("readthroughs"), job.user, book.id)

        if "include_reviews" in job.required:
            get_or_create_statuses(
                job.user, models.Review, data.get("reviews"), book.id
            )

        if "include_comments" in job.required:
            get_or_create_statuses(
                job.user, models.Comment, data.get("comments"), book.id
            )

        if "include_quotes" in job.required:
            get_or_create_statuses(
                job.user, models.Quotation, data.get("quotes"), book.id
            )
        if "include_lists" in job.required:
            upsert_lists(job.user, data.get("lists"), data.get("list_items"), book.id)


def get_or_create_edition(book_data, tar):
    """Take a JSON string of book and edition data,
    find or create the edition in the database and
    return an edition instance"""

    cover_path = book_data.get(
        "cover", None
    )  # we use this further down but need to assign a var before cleaning

    clean_book = clean_values(book_data)
    book = clean_book.copy()  # don't mutate the original book data

    # prefer edition values only if they are not null
    edition = clean_values(book["edition"])
    for key in edition.keys():
        if key not in book.keys() or (
            key in book.keys() and (edition[key] not in [None, ""])
        ):
            book[key] = edition[key]

    existing = find_existing(models.Edition, book, None)
    if existing:
        return existing

    # the book is not in the local database, so we have to do this the hard way
    local_authors = get_or_create_authors(book["authors"])

    # get rid of everything that's not strictly in a Book
    # or is many-to-many so can't be set directly
    associated_values = [
        "edition",
        "authors",
        "readthroughs",
        "shelves",
        "shelf_books",
        "lists",
        "list_items",
        "reviews",
        "comments",
        "quotes",
    ]

    for val in associated_values:
        del book[val]

    # now we can save the book as an Edition
    new_book = models.Edition.objects.create(**book)
    new_book.authors.set(local_authors)  # now we can add authors with set()

    # get cover from original book_data because we lost it in clean_values
    if cover_path:
        tar.write_image_to_file(cover_path, new_book.cover)

    # NOTE: clean_values removes "last_edited_by" because it's a user ID from the old database
    # if this is required, bookwyrm_export_job will need to bring in the user who edited it.

    # create parent
    work = models.Work.objects.create(title=book["title"])
    work.authors.set(local_authors)
    new_book.parent_work = work

    new_book.save(broadcast=False)
    return new_book


def clean_values(data):
    """clean values we don't want when creating new instances"""

    values = [
        "id",
        "pk",
        "remote_id",
        "cover",
        "preview_image",
        "last_edited_by",
        "last_edited_by_id",
        "user",
        "book_list",
        "shelf_book",
        "parent_work_id",
    ]

    common = data.keys() & values
    new_data = data
    for val in common:
        del new_data[val]
    return new_data


def find_existing(cls, data, user):
    """Given a book or author, find any existing model instances"""

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
    ]

    match_fields = []
    for i in identifiers:
        if data.get(i) not in [None, ""]:
            match_fields.append({i: data.get(i)})

    if len(match_fields) > 0:
        match = cls.objects.filter(reduce(operator.or_, (Q(**f) for f in match_fields)))
        return match.first()
    return None


def get_or_create_authors(data):
    """Take a JSON string of authors find or create the authors
    in the database and return a list of author instances"""

    authors = []
    for author in data:
        clean = clean_values(author)
        existing = find_existing(models.Author, clean, None)
        if existing:
            authors.append(existing)
        else:
            new = models.Author.objects.create(**clean)
            authors.append(new)
    return authors


def upsert_readthroughs(data, user, book_id):
    """Take a JSON string of readthroughs, find or create the
    instances in the database and return a list of saved instances"""

    for rt in data:
        start_date = (
            parse_datetime(rt["start_date"]) if rt["start_date"] is not None else None
        )
        finish_date = (
            parse_datetime(rt["finish_date"]) if rt["finish_date"] is not None else None
        )
        stopped_date = (
            parse_datetime(rt["stopped_date"])
            if rt["stopped_date"] is not None
            else None
        )
        readthrough = {
            "user": user,
            "book": models.Edition.objects.get(id=book_id),
            "progress": rt["progress"],
            "progress_mode": rt["progress_mode"],
            "start_date": start_date,
            "finish_date": finish_date,
            "stopped_date": stopped_date,
            "is_active": rt["is_active"],
        }

        existing = models.ReadThrough.objects.filter(**readthrough).exists()
        if not existing:
            models.ReadThrough.objects.create(**readthrough)


def get_or_create_statuses(user, cls, data, book_id):
    """Take a JSON string of a status and
    find or create the instances in the database"""

    for book_status in data:

        keys = [
            "content",
            "raw_content",
            "content_warning",
            "privacy",
            "sensitive",
            "published_date",
            "reading_status",
            "name",
            "rating",
            "quote",
            "raw_quote",
            "progress",
            "progress_mode",
            "position",
            "position_mode",
        ]
        common = book_status.keys() & keys
        status = {k: book_status[k] for k in common}
        status["published_date"] = parse_datetime(book_status["published_date"])
        if "rating" in common:
            status["rating"] = float(book_status["rating"])
        book = models.Edition.objects.get(id=book_id)
        exists = cls.objects.filter(**status, book=book, user=user).exists()
        if not exists:
            cls.objects.create(**status, book=book, user=user)


def upsert_lists(user, lists, items, book_id):
    """Take a list and ListItems as JSON and create DB entries if they don't already exist"""

    book = models.Edition.objects.get(id=book_id)

    for lst in lists:
        book_list = models.List.objects.filter(name=lst["name"], user=user).first()
        if not book_list:
            book_list = models.List.objects.create(
                user=user,
                name=lst["name"],
                description=lst["description"],
                curation=lst["curation"],
                privacy=lst["privacy"],
            )

        # If the list exists but the ListItem doesn't don't try to add it
        # with the same order as an existing item
        count = models.ListItem.objects.filter(book_list=book_list).count()

        for i in items[lst["name"]]:
            if not models.ListItem.objects.filter(
                book=book, book_list=book_list, user=user
            ).exists():
                models.ListItem.objects.create(
                    book=book,
                    book_list=book_list,
                    user=user,
                    notes=i["notes"],
                    order=i["order"] + count,
                )


def upsert_shelves(book, user, book_data):
    """Take shelf and ShelfBooks JSON objects and create
    DB entries if they don't already exist"""

    shelves = book_data["shelves"]

    for shelf in shelves:
        book_shelf = models.Shelf.objects.filter(name=shelf["name"], user=user).first()
        if not book_shelf:
            book_shelf = models.Shelf.objects.create(
                name=shelf["name"],
                user=user,
                identifier=shelf["identifier"],
                description=shelf["description"],
                editable=shelf["editable"],
                privacy=shelf["privacy"],
            )

        for shelfbook in book_data["shelf_books"][book_shelf.identifier]:

            shelved_date = parse_datetime(shelfbook["shelved_date"])

            if not models.ShelfBook.objects.filter(
                book=book, shelf=book_shelf, user=user
            ).exists():
                models.ShelfBook.objects.create(
                    book=book,
                    shelf=book_shelf,
                    user=user,
                    shelved_date=shelved_date,
                )


def update_user_profile(user, tar, data):
    """update the user's profile from import data"""
    name = data.get("name")
    username = data.get("username").split("@")[0]
    user.name = name if name else username
    user.summary = data.get("summary")
    user.save(update_fields=["name", "summary"])

    if data.get("avatar") is not None:
        avatar_filename = next(filter(lambda n: n.startswith("avatar"), tar.getnames()))
        tar.write_image_to_file(avatar_filename, user.avatar)


def update_user_settings(user, data):
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
        setattr(user, field, data[field])
    user.save(update_fields=update_fields)


@app.task(queue=IMPORTS, base=SubTask)
def update_user_settings_task(job_id, child_id):
    """wrapper task for user's settings import"""
    parent_job = BookwyrmImportJob.objects.get(id=job_id)

    return update_user_settings(parent_job.user, parent_job.import_data.get("user"))


def update_goals(user, data):
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


@app.task(queue=IMPORTS, base=SubTask)
def update_goals_task(job_id, child_id):
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
def upsert_saved_lists_task(job_id, child_id):
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
                # that means we should save to trigger a re-broadcast
                follow_request.save()


@app.task(queue=IMPORTS, base=SubTask)
def upsert_follows_task(job_id, child_id):
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
def upsert_user_blocks_task(job_id, child_id):
    """wrapper task for user's blocks import"""
    parent_job = BookwyrmImportJob.objects.get(id=job_id)

    return upsert_user_blocks(
        parent_job.user, parent_job.import_data.get("blocked_users")
    )
