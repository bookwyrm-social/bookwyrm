""" Let users export their book data """
import csv
import io
import json

from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.db.models import Q
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.views import View
from django.utils.decorators import method_decorator

from bookwyrm import models
from bookwyrm.settings import DOMAIN

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
        """Request json file"""
        return TemplateResponse(request, "preferences/export-json.html")

    def post(self, request):
        """Download the json file of a user's data"""

        # user
        s_user = {}
        vals = [
            "name",
            "summary",
            "manually_approves_followers",
            "hide_follows",
            "show_goal",
            "show_suggested_users",
            "discoverable",
            "preferred_timezone",
            "default_post_privacy",
        ]
        for k in vals:
            s_user[k] = getattr(request.user, k)
            s_user["avatar"] = f'https://{DOMAIN}{getattr(request.user, "avatar").url}'
        serialized_user = json.dumps(s_user)

        # reading goals
        reading_goals = models.AnnualGoal.objects.filter(user=request.user).distinct()
        goals_list = []
        try:
            for goal in reading_goals:
                goals_list.append(
                    {"goal": goal.goal, "year": goal.year, "privacy": goal.privacy}
                )
        except Exception:
            pass
        serialized_goals = json.dumps(goals_list)

        # read-throughs TODO!
        try:
            readthroughs = models.ReadThrough.objects.filter(
                user=request.user
            ).distinct()
            s_readthroughs = json.loads(
                serializers.serialize("json", readthroughs.all())
            )
            serialized_readthroughs = json.dumps(s_readthroughs["fields"])

        except Exception as e:
            serialized_readthroughs = []

        # books
        all_books = models.Edition.viewer_aware_objects(request.user)
        editions = all_books.filter(
            Q(shelves__user=request.user)
            | Q(readthrough__user=request.user)
            | Q(review__user=request.user)
        ).distinct()
        books = models.Book.objects.filter(id__in=editions).distinct()

        final_books = []

        for b in books:
            # books - TODO: probably should serialize books and editions together
            book = {"book": serializers.serialize("json", [b])}
            edition = (e for e in editions if b.id == e.id)
            book["edition"] = serializers.serialize("json", [next(edition)])
            # authors
            book["authors"] = serializers.serialize("json", b.authors.all())
            # readthroughs
            readthroughs = models.ReadThrough.objects.filter(
                user=request.user, book=b
            ).distinct()
            book["readthroughs"] = serializers.serialize("json", readthroughs.all())
            # shelves
            shelf_books = models.ShelfBook.objects.filter(
                user=request.user, book=b
            ).distinct()
            shelves_from_books = models.Shelf.objects.filter(shelfbook__in=shelf_books)
            book["shelves"] = serializers.serialize(
                "json", {*shelves_from_books.all(), *shelf_books.all()}
            )
            # book lists
            list_items = models.ListItem.objects.filter(
                user=request.user, book=b
            ).distinct()
            book_lists = models.List.objects.filter(id__in=list_items).distinct()
            book["lists"] = serializers.serialize(
                "json", {*book_lists.all(), *list_items.all()}
            )
            # reviews
            reviews = models.Review.objects.filter(user=request.user, book=b).distinct()
            statuses = models.Status.objects.filter(id__in=reviews).distinct()
            book["reviews"] = serializers.serialize(
                "json", {*reviews.all(), *statuses.all()}
            )
            # append everything
            final_books.append(book)
        serialized_books = json.dumps(final_books)

        # saved book lists
        saved_lists = models.List.objects.filter(
            id__in=request.user.saved_lists.all()
        ).distinct()
        serialized_saved_lists = json.dumps([l.remote_id for l in saved_lists])

        # follows
        follows = models.UserFollows.objects.filter(
            user_subject=request.user
        ).distinct()
        following = models.User.objects.filter(
            userfollows_user_object__in=follows
        ).distinct()
        serialized_follows = json.dumps([f.remote_id for f in following])

        data = f'{{"user": {serialized_user}, "goals": {serialized_goals}, "books": {serialized_books}, "saved_lists": {serialized_saved_lists}, "follows": {serialized_follows} }}'

        return HttpResponse(
            data,
            content_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="bookwyrm-account-export.json"'
            },
        )

    def get_fields_for_each(self, data):
        return_value = []
        if len(data) > 0:
            for val in data:
                r_data = val["fields"]
                r_data["pk"] = val["pk"]
                return_value.append(r_data)
            return return_value
        else:
            return
