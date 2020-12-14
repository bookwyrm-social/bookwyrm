''' handle reading a csv from goodreads '''
import csv
import logging

from bookwyrm import outgoing
from bookwyrm.tasks import app
from bookwyrm.models import ImportJob, ImportItem
from bookwyrm.status import create_notification

logger = logging.getLogger(__name__)
# TODO: remove or increase once we're confident it's not causing problems.
MAX_ENTRIES = 500


def create_job(user, csv_file, include_reviews, privacy):
    ''' check over a csv and creates a database entry for the job'''
    job = ImportJob.objects.create(
        user=user,
        include_reviews=include_reviews,
        privacy=privacy
    )
    for index, entry in enumerate(list(csv.DictReader(csv_file))[:MAX_ENTRIES]):
        if not all(x in entry for x in ('ISBN13', 'Title', 'Author')):
            raise ValueError('Author, title, and isbn must be in data.')
        ImportItem(job=job, index=index, data=entry).save()
    return job

def create_retry_job(user, original_job, items):
    ''' retry items that didn't import '''
    job = ImportJob.objects.create(
        user=user,
        include_reviews=original_job.include_reviews,
        privacy=original_job.privacy,
        retry=True
    )
    for item in items:
        ImportItem(job=job, index=item.index, data=item.data).save()
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
            except Exception as e:# pylint: disable=broad-except
                logger.exception(e)
                item.fail_reason = 'Error loading book'
                item.save()
                continue

            if item.book:
                item.save()
                results.append(item)

                # shelves book and handles reviews
                outgoing.handle_imported_book(
                    job.user, item, job.include_reviews, job.privacy)
            else:
                item.fail_reason = 'Could not find a match for book'
                item.save()
    finally:
        create_notification(job.user, 'IMPORT', related_import=job)
