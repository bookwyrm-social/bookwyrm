''' handle reading a csv from goodreads '''
import csv
from requests import HTTPError

from bookwyrm import outgoing
from bookwyrm.tasks import app
from bookwyrm.models import ImportJob, ImportItem
from bookwyrm.status import create_notification

# TODO: remove or increase once we're confident it's not causing problems.
MAX_ENTRIES = 500


def create_job(user, csv_file):
    ''' check over a csv and creates a database entry for the job'''
    job = ImportJob.objects.create(user=user)
    for index, entry in enumerate(list(csv.DictReader(csv_file))[:MAX_ENTRIES]):
        if not all(x in entry for x in ('ISBN13', 'Title', 'Author')):
            raise ValueError("Author, title, and isbn must be in data.")
        ImportItem(job=job, index=index, data=entry).save()
    return job


def start_import(job):
    ''' initalizes a csv import job '''
    result = import_data.delay(job.id)
    job.task_id = result.id
    job.save()


@app.task
def import_data(job_id):
    ''' does the actual lookup work in a celery task '''
    job = ImportJob.objects.get(id=job_id)
    try:
        results = []
        for item in job.items.all():
            try:
                item.resolve()
            except HTTPError:
                pass
            if item.book:
                item.save()
                results.append(item)
            else:
                item.fail_reason = "Could not match book on OpenLibrary"
                item.save()

        status = outgoing.handle_import_books(job.user, results)
        if status:
            job.import_status = status
            job.save()
    finally:
        create_notification(job.user, 'IMPORT', related_import=job)
