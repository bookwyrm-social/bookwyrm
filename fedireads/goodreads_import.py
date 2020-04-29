''' handle reading a csv from goodreads '''
import csv
from requests import HTTPError

from fedireads import outgoing
from fedireads.tasks import app
from fedireads.models import ImportJob, ImportItem
from fedireads.status import create_notification

# TODO: remove or notify about this in the UI
MAX_ENTRIES = 20


def create_job(user, csv_file):
    job = ImportJob.objects.create(user=user)
    for index, entry in enumerate(list(csv.DictReader(csv_file))[:MAX_ENTRIES]):
        if not all(x in entry for x in ('ISBN13', 'Title', 'Author')):
            raise ValueError("Author, title, and isbn must be in data.")
        ImportItem(job=job, index=index, data=entry).save()
    return job

def start_import(job):
    result = import_data.delay(job.id)
    job.task_id = result.id
    job.save()

@app.task
def import_data(job_id):
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
