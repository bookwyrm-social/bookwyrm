""" Let users export their book data """
from datetime import timedelta
import csv
import datetime
import io

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, ExpressionWrapper, F
from django.db.models.fields import DurationField
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseServerError, Http404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.shortcuts import redirect

from storages.backends.s3 import S3Storage

from bookwyrm import models, settings
from bookwyrm.models.bookwyrm_export_job import BookwyrmExportJob
from bookwyrm.utils.cache import get_or_set

# pylint: disable=no-self-use,too-many-locals
@method_decorator(login_required, name="dispatch")
class Export(View):
    """Let users export data"""

    def get(self, request):
        """Request csv file"""
        return TemplateResponse(request, "preferences/export.html")

    def post(self, request):
        """Download the csv file of a user's book data"""
        books = models.Edition.viewer_aware_objects(request.user)
        books_shelves = books.filter(Q(shelves__user=request.user)).distinct()
        books_readthrough = books.filter(Q(readthrough__user=request.user)).distinct()
        books_review = books.filter(Q(review__user=request.user)).distinct()
        books_comment = books.filter(Q(comment__user=request.user)).distinct()
        books_quotation = books.filter(Q(quotation__user=request.user)).distinct()

        books = set(
            list(books_shelves)
            + list(books_readthrough)
            + list(books_review)
            + list(books_comment)
            + list(books_quotation)
        )

        csv_string = io.StringIO()
        writer = csv.writer(csv_string)

        deduplication_fields = [
            f.name
            for f in models.Edition._meta.get_fields()  # pylint: disable=protected-access
            if getattr(f, "deduplication_field", False)
        ]
        fields = (
            ["title", "author_text"]
            + deduplication_fields
            + [
                "start_date",
                "finish_date",
                "stopped_date",
                "rating",
                "review_name",
                "review_cw",
                "review_content",
                "review_published",
                "shelf",
                "shelf_name",
                "shelf_date",
            ]
        )
        writer.writerow(fields)

        for book in books:
            # I think this is more efficient than doing a subquery in the view? but idk
            review_rating = (
                models.Review.objects.filter(
                    user=request.user, book=book, rating__isnull=False
                )
                .order_by("-published_date")
                .first()
            )

            book.rating = review_rating.rating if review_rating else None

            readthrough = (
                models.ReadThrough.objects.filter(user=request.user, book=book)
                .order_by("-start_date", "-finish_date")
                .first()
            )
            if readthrough:
                book.start_date = (
                    readthrough.start_date.date() if readthrough.start_date else None
                )
                book.finish_date = (
                    readthrough.finish_date.date() if readthrough.finish_date else None
                )
                book.stopped_date = (
                    readthrough.stopped_date.date()
                    if readthrough.stopped_date
                    else None
                )

            review = (
                models.Review.objects.filter(
                    user=request.user, book=book, content__isnull=False
                )
                .order_by("-published_date")
                .first()
            )
            if review:
                book.review_published = (
                    review.published_date.date() if review.published_date else None
                )
                book.review_name = review.name
                book.review_cw = review.content_warning
                book.review_content = (
                    review.raw_content if review.raw_content else review.content
                )  # GoodReads imported reviews do not have raw_content, but content.

            shelfbook = (
                models.ShelfBook.objects.filter(user=request.user, book=book)
                .order_by("-shelved_date", "-created_date", "-updated_date")
                .last()
            )
            if shelfbook:
                book.shelf = shelfbook.shelf.identifier
                book.shelf_name = shelfbook.shelf.name
                book.shelf_date = (
                    shelfbook.shelved_date.date() if shelfbook.shelved_date else None
                )

            writer.writerow([getattr(book, field, "") or "" for field in fields])

        return HttpResponse(
            csv_string.getvalue(),
            content_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="bookwyrm-export.csv"'
            },
        )


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class ExportUser(View):
    """
    Let users request and download an archive of user data to import into
    another Bookwyrm instance.
    """

    user_jobs = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

        self.user_jobs = BookwyrmExportJob.objects.filter(user=request.user).order_by(
            "-created_date"
        )

    def new_export_blocked_until(self):
        """whether the user is allowed to request a new export"""
        last_job = self.user_jobs.first()
        if not last_job:
            return None
        site = models.SiteSettings.objects.get()
        blocked_until = last_job.created_date + timedelta(
            hours=site.user_import_time_limit
        )
        return blocked_until if blocked_until > timezone.now() else None

    def get(self, request):
        """Request tar file"""

        exports = []
        for job in self.user_jobs:
            export = {"job": job}

            if job.export_data:
                try:
                    export["size"] = job.export_data.size
                    export["url"] = reverse("prefs-export-file", args=[job.task_id])
                # pylint: disable=broad-exception-caught
                except (
                    FileNotFoundError,
                    Exception,
                ):
                    # file no longer exists
                    export["url"] = None

            exports.append(export)

        next_available = self.new_export_blocked_until()
        paginated = Paginator(exports, settings.PAGE_LENGTH)
        site = models.SiteSettings.objects.get()
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "jobs": page,
            "next_available": next_available,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "expiry_hours": site.export_files_lifetime_hours,
        }

        seconds = get_or_set(
            "avg-user-export-time", get_average_export_time, timeout=86400
        )
        if seconds and seconds > 60**2:
            data["recent_avg_hours"] = seconds / (60**2)
        elif seconds:
            data["recent_avg_minutes"] = seconds / 60

        return TemplateResponse(request, "preferences/export-user.html", data)

    def post(self, request):
        """Trigger processing of a new user export file"""
        if self.new_export_blocked_until() is not None:
            return HttpResponse(status=429)  # Too Many Requests

        job = BookwyrmExportJob.objects.create(user=request.user)
        job.start_job()

        return redirect("prefs-user-export")


@method_decorator(login_required, name="dispatch")
class ExportArchive(View):
    """Serve the archive file"""

    def get(self, request, archive_id):
        """download user export file"""
        export = BookwyrmExportJob.objects.get(task_id=archive_id, user=request.user)

        if settings.USE_S3:
            # make custom_domain None so we can sign the url
            # see https://github.com/jschneier/django-storages/issues/944
            storage = S3Storage(querystring_auth=True, custom_domain=None)
            try:
                url = S3Storage.url(
                    storage,
                    f"/exports/{export.task_id}.tar.gz",
                    expire=settings.S3_SIGNED_URL_EXPIRY,
                )
            except Exception:
                raise Http404()
            return redirect(url)

        if settings.USE_AZURE:
            # not implemented
            return HttpResponseServerError()

        try:
            return HttpResponse(
                export.export_data,
                content_type="application/gzip",
                headers={
                    # pylint: disable=line-too-long
                    "Content-Disposition": 'attachment; filename="bookwyrm-account-export.tar.gz"'
                },
            )
        except FileNotFoundError:
            raise Http404()


def get_average_export_time() -> float:
    """Helper to figure out how long exports are taking (returns seconds)"""
    last_week = timezone.now() - datetime.timedelta(days=7)
    recent_avg = (
        models.BookwyrmExportJob.objects.filter(
            created_date__gte=last_week, complete=True
        )
        .exclude(status="stopped")
        .annotate(
            runtime=ExpressionWrapper(
                F("updated_date") - F("created_date"),
                output_field=DurationField(),
            )
        )
        .aggregate(Avg("runtime"))
        .get("runtime__avg")
    )

    if recent_avg:
        return recent_avg.total_seconds()
    return None
