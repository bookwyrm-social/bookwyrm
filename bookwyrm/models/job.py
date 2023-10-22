"""Everything needed for Celery to multi-thread complex tasks."""

from django.db import models
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from bookwyrm.models.user import User

from bookwyrm.tasks import app


class Job(models.Model):
    """Abstract model to store the state of a Task."""

    class Status(models.TextChoices):
        """Possible job states."""

        PENDING = "pending", _("Pending")
        ACTIVE = "active", _("Active")
        COMPLETE = "complete", _("Complete")
        STOPPED = "stopped", _("Stopped")
        FAILED = "failed", _("Failed")

    task_id = models.UUIDField(unique=True, null=True, blank=True)

    created_date = models.DateTimeField(default=timezone.now)
    updated_date = models.DateTimeField(default=timezone.now)
    complete = models.BooleanField(default=False)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PENDING, null=True
    )

    class Meta:
        """Make it abstract"""

        abstract = True

    def complete_job(self):
        """Report that the job has completed"""
        if self.complete:
            return

        self.status = self.Status.COMPLETE
        self.complete = True
        self.updated_date = timezone.now()

        self.save(update_fields=["status", "complete", "updated_date"])

    def stop_job(self, reason=None):
        """Stop the job"""
        if self.complete:
            return

        self.__terminate_job()

        if reason and reason == "failed":
            self.status = self.Status.FAILED
        else:
            self.status = self.Status.STOPPED
        self.complete = True
        self.updated_date = timezone.now()

        self.save(update_fields=["status", "complete", "updated_date"])

    def set_status(self, status):
        """Set job status"""
        if self.complete:
            return

        if self.status == status:
            return

        if status == self.Status.COMPLETE:
            self.complete_job()
            return

        if status == self.Status.STOPPED:
            self.stop_job()
            return

        if status == self.Status.FAILED:
            self.stop_job(reason="failed")
            return

        self.updated_date = timezone.now()
        self.status = status

        self.save(update_fields=["status", "updated_date"])

    def __terminate_job(self):
        """Tell workers to ignore and not execute this task."""
        app.control.revoke(self.task_id, terminate=True)


class ParentJob(Job):
    """Store the state of a Task which can spawn many :model:`ChildJob`s to spread
    resource load.

    Intended to be sub-classed if necessary via proxy or
    multi-table inheritance.
    Extends :model:`Job`.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def complete_job(self):
        """Report that the job has completed and stop pending
        children. Extend.
        """
        super().complete_job()
        self.__terminate_pending_child_jobs()

    def notify_child_job_complete(self):
        """let the job know when the items get work done"""
        if self.complete:
            return

        self.updated_date = timezone.now()
        self.save(update_fields=["updated_date"])

        if not self.complete and self.has_completed:
            self.complete_job()

    def __terminate_job(self):  # pylint: disable=unused-private-member
        """Tell workers to ignore and not execute this task
        & pending child tasks. Extend.
        """
        super().__terminate_job()
        self.__terminate_pending_child_jobs()

    def __terminate_pending_child_jobs(self):
        """Tell workers to ignore and not execute any pending child tasks."""
        tasks = self.pending_child_jobs.filter(task_id__isnull=False).values_list(
            "task_id", flat=True
        )
        app.control.revoke(list(tasks))

        for task in self.pending_child_jobs:
            task.update(status=self.Status.STOPPED)

    @property
    def has_completed(self):
        """has this job finished"""
        return not self.pending_child_jobs.exists()

    @property
    def pending_child_jobs(self):
        """items that haven't been processed yet"""
        return self.child_jobs.filter(complete=False)


class ChildJob(Job):
    """Stores the state of a Task for the related :model:`ParentJob`.

    Intended to be sub-classed if necessary via proxy or
    multi-table inheritance.
    Extends :model:`Job`.
    """

    parent_job = models.ForeignKey(
        ParentJob, on_delete=models.CASCADE, related_name="child_jobs"
    )

    def set_status(self, status):
        """Set job and parent_job status. Extend."""
        super().set_status(status)

        if (
            status == self.Status.ACTIVE
            and self.parent_job.status == self.Status.PENDING
        ):
            self.parent_job.set_status(self.Status.ACTIVE)

    def complete_job(self):
        """Report to parent_job that the job has completed. Extend."""
        super().complete_job()
        self.parent_job.notify_child_job_complete()


class ParentTask(app.Task):
    """Used with ParentJob, Abstract Tasks execute code at specific points in
    a Task's lifecycle, applying to all Tasks with the same 'base'.

    All status & ParentJob.task_id assignment is managed here for you.
    Usage e.g. @app.task(base=ParentTask)
    """

    def before_start(
        self, task_id, args, kwargs
    ):  # pylint: disable=no-self-use, unused-argument
        """Handler called before the task starts. Override.

        Prepare ParentJob before the task starts.

        Arguments:
            task_id (str): Unique id of the task to execute.
            args (Tuple): Original arguments for the task to execute.
            kwargs (Dict): Original keyword arguments for the task to execute.

        Keyword Arguments:
            job_id (int): Unique 'id' of the ParentJob.
            no_children (bool): If 'True' this is the only Task expected to run
                for the given ParentJob.

        Returns:
            None: The return value of this handler is ignored.
        """
        job = ParentJob.objects.get(id=kwargs["job_id"])
        job.task_id = task_id
        job.save(update_fields=["task_id"])

        if kwargs["no_children"]:
            job.set_status(ChildJob.Status.ACTIVE)

    def on_success(
        self, retval, task_id, args, kwargs
    ):  # pylint: disable=no-self-use, unused-argument
        """Run by the worker if the task executes successfully. Override.

        Update ParentJob on Task complete.

        Arguments:
            retval (Any): The return value of the task.
            task_id (str): Unique id of the executed task.
            args (Tuple): Original arguments for the executed task.
            kwargs (Dict): Original keyword arguments for the executed task.

        Keyword Arguments:
            job_id (int): Unique 'id' of the ParentJob.
            no_children (bool): If 'True' this is the only Task expected to run
                for the given ParentJob.

        Returns:
            None: The return value of this handler is ignored.
        """

        if kwargs["no_children"]:
            job = ParentJob.objects.get(id=kwargs["job_id"])
            job.complete_job()


class SubTask(app.Task):
    """Used with ChildJob, Abstract Tasks execute code at specific points in
    a Task's lifecycle, applying to all Tasks with the same 'base'.

    All status & ChildJob.task_id assignment is managed here for you.
    Usage e.g. @app.task(base=SubTask)
    """

    def before_start(
        self, task_id, args, kwargs
    ):  # pylint: disable=no-self-use, unused-argument
        """Handler called before the task starts. Override.

        Prepare ChildJob before the task starts.

        Arguments:
            task_id (str): Unique id of the task to execute.
            args (Tuple): Original arguments for the task to execute.
            kwargs (Dict): Original keyword arguments for the task to execute.

        Keyword Arguments:
            job_id (int): Unique 'id' of the ParentJob.
            child_id (int): Unique 'id' of the ChildJob.

        Returns:
            None: The return value of this handler is ignored.
        """
        child_job = ChildJob.objects.get(id=kwargs["child_id"])
        child_job.task_id = task_id
        child_job.save(update_fields=["task_id"])
        child_job.set_status(ChildJob.Status.ACTIVE)

    def on_success(
        self, retval, task_id, args, kwargs
    ):  # pylint: disable=no-self-use, unused-argument
        """Run by the worker if the task executes successfully. Override.

        Notify ChildJob of task completion.

        Arguments:
            retval (Any): The return value of the task.
            task_id (str): Unique id of the executed task.
            args (Tuple): Original arguments for the executed task.
            kwargs (Dict): Original keyword arguments for the executed task.

        Keyword Arguments:
            job_id (int): Unique 'id' of the ParentJob.
            child_id (int): Unique 'id' of the ChildJob.

        Returns:
            None: The return value of this handler is ignored.
        """
        subtask = ChildJob.objects.get(id=kwargs["child_id"])
        subtask.complete_job()


@transaction.atomic
def create_child_job(parent_job, task_callback):
    """Utility method for creating a ChildJob
    and running a task to avoid DB race conditions
    """
    child_job = ChildJob.objects.create(parent_job=parent_job)
    transaction.on_commit(
        lambda: task_callback.delay(job_id=parent_job.id, child_id=child_job.id)
    )

    return child_job
