"""cleanup tasks"""

import math
from datetime import datetime, timedelta, timezone

from django.db.models import (
    CharField,
    DateTimeField,
    IntegerField,
    ManyToManyField,
    TextChoices,
)
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from bookwyrm.models.job import ParentJob, ParentTask
from bookwyrm.connectors.abstract_connector import get_data
from bookwyrm.connectors.connector_manager import search
from bookwyrm.tasks import app, MISC
from bookwyrm.utils.images import set_cover_from_url


class CleanUpUserExportFilesJob(ParentJob):
    """A job to clean up old import and export files"""

    expiry_date = DateTimeField()
    tasks = IntegerField(default=0)
    completed_tasks = IntegerField(default=0)

    @property
    def percent_complete(self):
        """How far along?"""

        if not self.tasks:
            return 0
        return math.floor(self.completed_tasks / self.tasks * 100)

    def start_job(self):
        """schedule the tasks"""

        self.set_status("active")

        export_jobs = models.BookwyrmExportJob.objects.filter(
            complete=True, updated_date__lt=self.expiry_date
        )

        import_jobs = models.BookwyrmImportJob.objects.filter(
            complete=True, updated_date__lt=self.expiry_date
        )

        for export in export_jobs:
            if export.export_data.name:
                self.tasks += 1
                self.save(update_fields=["tasks"])
                delete_user_export_file_task.delay(job_id=self.id, export_id=export.id)

        for job in import_jobs:
            if job.archive_file.name:
                self.tasks += 1
                self.save(update_fields=["tasks"])
                delete_user_export_file_task.delay(job_id=self.id, import_id=job.id)

        if self.tasks == 0:
            self.complete_job()


class CleanUpExportsTask(ParentTask):
    """Task to delete expired user export files"""

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Handler called after the task returns"""

        job = CleanUpUserExportFilesJob.objects.get(id=kwargs["job_id"])
        job.completed_tasks += 1
        job.save(update_fields=["completed_tasks"])

        if job.completed_tasks == job.tasks:
            job.complete_job()


@app.task(queue=MISC, base=CleanUpExportsTask)
def delete_user_export_file_task(**kwargs):
    """A task to delete a specific export/import file"""

    if kwargs.get("import_id"):
        file = models.BookwyrmImportJob.objects.get(id=kwargs["import_id"])
        file.archive_file.delete()

    else:
        export_id = kwargs.get("export_id")
        if export_id:
            file = models.BookwyrmExportJob.objects.get(id=export_id)
            file.export_data.delete()


@app.task(queue=MISC)
def start_export_deletions(**kwargs):
    """trigger the job from scheduler"""

    user = models.User.objects.get(id=kwargs["user"])
    site = models.SiteSettings.objects.get()
    hours = site.export_files_lifetime_hours

    expiry_date = datetime.now(timezone.utc) - timedelta(hours=hours)
    job = CleanUpUserExportFilesJob.objects.create(user=user, expiry_date=expiry_date)

    job.start_job()


class FindMissingCoversJob(ParentJob):
    """Job to search the fedi for covers we don't have"""

    class JobType(TextChoices):
        """Possible status types."""

        MISSING = "missing", _("Missing")
        WRONG_PATH = "wrong_path", _("Wrong Path")

    job_type = CharField(
        max_length=10, choices=JobType.choices, default=JobType.MISSING, null=True
    )
    editions = ManyToManyField(
        models.Edition,
        related_name="missing_covers_job",
    )
    found_covers = ManyToManyField(
        models.Edition,
        related_name="+",
    )

    completed_tasks = IntegerField(default=0)

    def start_job(self):
        """Report that the job has started and trigger subtasks"""

        self.set_status("active")

        for edition in self.editions.all():
            get_missing_cover_task.delay(job_id=self.id, edition_id=edition.id)

        if self.editions.count() == 0:
            self.complete_job()


class MissingCoverTask(ParentTask):
    """Task to find a cover for an individual edition"""

    def on_success(self, retval, task_id, args, kwargs):
        """Override from ParentTask. Save edition to found_covers if we found one"""

        if retval:
            job = FindMissingCoversJob.objects.get(id=kwargs["job_id"])
            edition = models.Edition.objects.get(id=kwargs["edition_id"])

            job.found_covers.add(edition)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Handler called after the task returns"""

        job = FindMissingCoversJob.objects.get(id=kwargs["job_id"])
        job.completed_tasks += 1
        job.save(update_fields=["completed_tasks"])

        if job.completed_tasks == job.editions.count():
            job.complete_job()


@app.task(queue=MISC, base=MissingCoverTask)
def get_missing_cover_task(**kwargs):
    """trigger the child tasks for each edition"""

    job = FindMissingCoversJob.objects.get(id=kwargs["job_id"])
    edition = models.Edition.objects.get(id=kwargs["edition_id"])

    if job.status == "stopped":
        return None

    return get_cover_from_identifiers(edition=edition)


def get_cover_from_identifiers(edition):
    """for a given edition, can we find a book cover from the fedi?"""

    # idk there is probably a more pythonic way of doing this

    fields = [
        f.name
        for f in models.Edition._meta.get_fields()
        if hasattr(f, "deduplication_field") and f.deduplication_field
    ]

    for field in fields:
        query_result = (
            search(query=getattr(edition, field), min_confidence=0.999) or None
        )
        if not query_result:
            continue

        for search_result in query_result:
            for result in search_result["results"]:
                data = get_data(getattr(result, "key"))

                if data and data.get("cover"):
                    if data.get("cover").get("url") in ["", None]:
                        continue

                    url = data["cover"]["url"]
                    image = set_cover_from_url(url)
                    if image:
                        edition.cover.save(*image)
                        return edition.id

    return None


def get_covers_with_incorrect_filepaths():
    """return a queryset of all books where the name path doesn't resolve"""

    has_cover = models.Edition.objects.exclude(cover="")
    wrong_path_ids = [
        x.id for x in has_cover if not x.cover.storage.exists(x.cover.name)
    ]

    return models.Edition.objects.filter(id__in=wrong_path_ids)


@app.task(queue=MISC)
def run_missing_covers_job(**kwargs):
    """create and start a FindMissingCoversJob"""

    job_type = kwargs.get("type", "missing")

    if job_type == "wrong_path":
        editions = get_covers_with_incorrect_filepaths()
    else:
        editions = models.Edition.objects.filter(cover="")

    job = FindMissingCoversJob.objects.create(
        user_id=kwargs["user_id"], job_type=job_type
    )
    job.editions.set(editions)

    job.start_job()
