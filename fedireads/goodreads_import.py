''' handle reading a csv from goodreads '''
import csv
from requests import HTTPError

from fedireads import outgoing
from fedireads.tasks import app
from fedireads.models import ImportJob, ImportItem


# TODO: remove or notify about this in the UI
MAX_ENTRIES = 20


def create_job(user, csv_file):
    job = ImportJob.objects.create(user=user)
    for index, entry in enumerate(list(csv.DictReader(csv_file))[:MAX_ENTRIES]):
        ImportItem(job=job, index=index, data=entry).save()
    return job

def start_import(job):
    result = import_data.delay(job.id)
    job.task_id = result.id
    job.save()

@app.task
def import_data(job_id):
    job = ImportJob.objects.get(id=job_id)
    user = job.user
    results = []
    reviews = []
    for item in job.items.all():
        try:
            item.resolve()
        except HTTPError:
            pass
        if item.book:
            item.save()
            results.append(item)
            if item.rating or item.review:
                reviews.append(item)
        else:
            item.fail_reason = "Could not match book on OpenLibrary"
            item.save()

    outgoing.handle_import_books(user, results)
    for item in reviews:
        review_title = "Review of {!r} on Goodreads".format(
            item.book.title,
        ) if item.review else ""
        outgoing.handle_review(
            user,
            item.book,
            review_title,
            item.review,
            item.rating,
        )
