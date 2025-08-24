""" cleanup tasks """
import math
from datetime import datetime, timedelta, timezone

from django.db.models import DateTimeField, IntegerField

from bookwyrm.tasks import app, MISC
from bookwyrm import models
from bookwyrm.models.job import ParentJob, ParentTask


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

    # pylint: disable=too-many-arguments, unused-argument, no-self-use
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
