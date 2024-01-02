""" Let users export their book data """
from datetime import timedelta
import csv
import io

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator
from django.shortcuts import redirect

from bookwyrm import models
from bookwyrm.models.bookwyrm_export_job import BookwyrmExportJob
from bookwyrm.settings import PAGE_LENGTH

# pylint: disable=no-self-use
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
            + ["rating", "review_name", "review_cw", "review_content"]
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

            review = (
                models.Review.objects.filter(
                    user=request.user, book=book, content__isnull=False
                )
                .order_by("-published_date")
                .first()
            )
            if review:
                book.review_name = review.name
                book.review_cw = review.content_warning
                book.review_content = review.raw_content
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
    """Let users export user data to import into another Bookwyrm instance"""

    def get(self, request):
        """Request tar file"""

        jobs = BookwyrmExportJob.objects.filter(user=request.user).order_by(
            "-created_date"
        )
        site = models.SiteSettings.objects.get()
        hours = site.user_import_time_limit
        allowed = (
            jobs.first().created_date < timezone.now() - timedelta(hours=hours)
            if jobs.first()
            else True
        )
        next_available = (
            jobs.first().created_date + timedelta(hours=hours) if not allowed else False
        )
        paginated = Paginator(jobs, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "jobs": page,
            "next_available": next_available,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
        }

        return TemplateResponse(request, "preferences/export-user.html", data)

    def post(self, request):
        """Download the json file of a user's data"""

        job = BookwyrmExportJob.objects.create(user=request.user)
        job.start_job()

        return redirect("prefs-user-export")


@method_decorator(login_required, name="dispatch")
class ExportArchive(View):
    """Serve the archive file"""

    def get(self, request, archive_id):
        """download user export file"""
        export = BookwyrmExportJob.objects.get(task_id=archive_id, user=request.user)
        return HttpResponse(
            export.export_data,
            content_type="application/gzip",
            headers={
                "Content-Disposition": 'attachment; filename="bookwyrm-account-export.tar.gz"'  # pylint: disable=line-too-long
            },
        )
