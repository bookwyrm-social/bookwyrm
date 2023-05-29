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
class ExportJson(View):
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
                goals_list.append({"goal": goal.goal, "year": goal.year, "privacy": goal.privacy})
        except Exception: 
            pass
        serialized_goals = json.dumps(goals_list)

        # read-throughs
        try:
            readthroughs = models.ReadThrough.objects.filter(user=request.user).distinct()
            s_readthroughs = json.loads(serializers.serialize('json', readthroughs.all()))
            serialized_readthroughs = json.dumps(s_readthroughs["fields"])

        except Exception as e:
            serialized_readthroughs = []

        # books
        books = models.Edition.viewer_aware_objects(request.user)
        editions_for_export = books.filter(
            Q(shelves__user=request.user) |
            Q(readthrough__user=request.user) |
            Q(review__user=request.user)    
        ).distinct()
        eds = json.loads(serializers.serialize('json', editions_for_export.all()))
        editions = self.get_fields_for_each(eds)
        books_for_export = models.Book.objects.filter(id__in=editions_for_export).distinct()
        bks = json.loads(serializers.serialize('json', books_for_export.all()))
        books = self.get_fields_for_each(bks)

        final_books =[]

        for book in books:
            # editions
            for edition in editions:
                if book["pk"] == edition["pk"]:
                    book.update(edition)
            # authors
            b_authors = book["authors"]
            authors = models.Author.objects.filter(id__in=b_authors)
            serialized_authors = json.loads(serializers.serialize("json", authors.all()))
            author_fields = []
            for author in serialized_authors:
                author_fields.append(author["fields"])
            book["authors"] = []
            book["extra"] = {}
            book["extra"]["authors"] = author_fields

            # shelves 
            shelf_books = models.ShelfBook.objects.filter(user=request.user, book_id=book["pk"]).distinct()
            serialized_shelf_books = json.loads(serializers.serialize("json", shelf_books.all()))
            shelves_from_books = models.Shelf.objects.filter(shelfbook__in=shelf_books)
            serialized_shelves_from_books = json.loads(serializers.serialize("json", shelves_from_books.all()))
            
            shelf_book_list = []
            for b in serialized_shelf_books:
                shelf_book = b["fields"]
                for s in serialized_shelves_from_books:
                    if s["pk"] == shelf_book["shelf"]:
                        shelf_book["shelf"] = s["fields"]
                
                shelf_book_list.append(shelf_book)
            book["extra"]["shelf_books"] = shelf_book_list

            # book lists
            list_items = models.ListItem.objects.filter(user=request.user, book_id=book["pk"]).distinct()
            serialized_items = json.loads(serializers.serialize("json", list_items.all()))
            book_lists = models.List.objects.filter(id__in=list_items).distinct()
            serialized_lists = json.loads(serializers.serialize("json", book_lists.all()))
            booklist_items = []
            for i in serialized_items:
                item = i["fields"]
                for l in serialized_lists:
                    if item["book_list"] == l["pk"]:
                        item["book_list"] = l["fields"]
                booklist_items.append(item)
            book["extra"]["list_items"] = booklist_items

            # reviews
            reviews = models.Review.objects.filter(user=request.user, book_id=book["pk"]).distinct()
            serialized_reviews = json.loads(serializers.serialize("json", reviews.all()))
            book_reviews = []
            for r in serialized_reviews:
                status = models.Status.objects.get(id=r["pk"])
                serialized_status = json.loads(serializers.serialize("json", [status]))
                review = r["fields"]
                detail = serialized_status[0]["fields"]
                review.update(detail)
                book_reviews.append(review)
            book["extra"]["reviews"] = book_reviews

            # append everything
            final_books.append(book)
        serialized_books = json.dumps(final_books)

        # saved book lists
        saved_lists = models.List.objects.filter(id__in=request.user.saved_lists.all()).distinct()
        serialized_saved_lists = json.dumps([l.remote_id for l in saved_lists])

        # follows
        follows = models.UserFollows.objects.filter(user_subject=request.user).distinct()
        following = models.User.objects.filter(userfollows_user_object__in=follows).distinct()
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