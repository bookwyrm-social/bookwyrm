""" the good stuff! the books! """
from uuid import uuid4

from dateutil.parser import parse as dateparse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.postgres.search import SearchRank, SearchVector
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Q
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.connectors import connector_manager
from bookwyrm.connectors.abstract_connector import get_image
from bookwyrm.settings import PAGE_LENGTH
from .helpers import is_api_request, get_edition, privacy_filter


# pylint: disable= no-self-use
class Book(View):
    """a book! this is the stuff"""

    def get(self, request, book_id, user_statuses=False):
        """info about a book"""
        user_statuses = user_statuses if request.user.is_authenticated else False
        try:
            book = models.Book.objects.select_subclasses().get(id=book_id)
        except models.Book.DoesNotExist:
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(book.to_activity())

        if isinstance(book, models.Work):
            book = book.default_edition
        if not book or not book.parent_work:
            return HttpResponseNotFound()

        work = book.parent_work

        # all reviews for the book
        reviews = privacy_filter(
            request.user, models.Review.objects.filter(book__in=work.editions.all())
        )

        # the reviews to show
        if user_statuses:
            if user_statuses == "review":
                queryset = book.review_set.select_subclasses()
            elif user_statuses == "comment":
                queryset = book.comment_set
            else:
                queryset = book.quotation_set
            queryset = queryset.filter(user=request.user)
        else:
            queryset = reviews.exclude(Q(content__isnull=True) | Q(content=""))
        queryset = queryset.select_related("user")
        paginated = Paginator(queryset, PAGE_LENGTH)

        data = {
            "book": book,
            "statuses": paginated.get_page(request.GET.get("page")),
            "review_count": reviews.count(),
            "ratings": reviews.filter(
                Q(content__isnull=True) | Q(content="")
            ).select_related("user")
            if not user_statuses
            else None,
            "rating": reviews.aggregate(Avg("rating"))["rating__avg"],
            "lists": privacy_filter(
                request.user, book.list_set.filter(listitem__approved=True)
            ),
        }

        if request.user.is_authenticated:
            readthroughs = models.ReadThrough.objects.filter(
                user=request.user,
                book=book,
            ).order_by("start_date")

            for readthrough in readthroughs:
                readthrough.progress_updates = (
                    readthrough.progressupdate_set.all().order_by("-updated_date")
                )
            data["readthroughs"] = readthroughs

            data["user_shelfbooks"] = models.ShelfBook.objects.filter(
                user=request.user, book=book
            ).select_related("shelf")

            data["other_edition_shelves"] = models.ShelfBook.objects.filter(
                ~Q(book=book),
                user=request.user,
                book__parent_work=book.parent_work,
            ).select_related("shelf", "book")

            data["user_statuses"] = {
                "review_count": book.review_set.filter(user=request.user).count(),
                "comment_count": book.comment_set.filter(user=request.user).count(),
                "quotation_count": book.quotation_set.filter(user=request.user).count(),
            }

        return TemplateResponse(request, "book/book.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class EditBook(View):
    """edit a book"""

    def get(self, request, book_id=None):
        """info about a book"""
        book = None
        if book_id:
            book = get_edition(book_id)
            if not book.description:
                book.description = book.parent_work.description
        data = {"book": book, "form": forms.EditionForm(instance=book)}
        return TemplateResponse(request, "book/edit_book.html", data)

    def post(self, request, book_id=None):
        """edit a book cool"""
        # returns None if no match is found
        book = models.Edition.objects.filter(id=book_id).first()
        form = forms.EditionForm(request.POST, request.FILES, instance=book)

        data = {"book": book, "form": form}
        if not form.is_valid():
            return TemplateResponse(request, "book/edit_book.html", data)

        add_author = request.POST.get("add_author")
        # we're adding an author through a free text field
        if add_author:
            data["add_author"] = add_author
            data["author_matches"] = []
            for author in add_author.split(","):
                if not author:
                    continue
                # check for existing authors
                vector = SearchVector("name", weight="A") + SearchVector(
                    "aliases", weight="B"
                )

                data["author_matches"].append(
                    {
                        "name": author.strip(),
                        "matches": (
                            models.Author.objects.annotate(search=vector)
                            .annotate(rank=SearchRank(vector, author))
                            .filter(rank__gt=0.4)
                            .order_by("-rank")[:5]
                        ),
                    }
                )

        # we're creating a new book
        if not book:
            # check if this is an edition of an existing work
            author_text = book.author_text if book else add_author
            data["book_matches"] = connector_manager.local_search(
                "%s %s" % (form.cleaned_data.get("title"), author_text),
                min_confidence=0.5,
                raw=True,
            )[:5]

        # either of the above cases requires additional confirmation
        if add_author or not book:
            # creting a book or adding an author to a book needs another step
            data["confirm_mode"] = True
            # this isn't preserved because it isn't part of the form obj
            data["remove_authors"] = request.POST.getlist("remove_authors")
            # make sure the dates are passed in as datetime, they're currently a string
            # QueryDicts are immutable, we need to copy
            formcopy = data["form"].data.copy()
            try:
                formcopy["first_published_date"] = dateparse(
                    formcopy["first_published_date"]
                )
            except (MultiValueDictKeyError, ValueError):
                pass
            try:
                formcopy["published_date"] = dateparse(formcopy["published_date"])
            except (MultiValueDictKeyError, ValueError):
                pass
            data["form"].data = formcopy
            return TemplateResponse(request, "book/edit_book.html", data)

        remove_authors = request.POST.getlist("remove_authors")
        for author_id in remove_authors:
            book.authors.remove(author_id)

        book = form.save(commit=False)
        url = request.POST.get("cover-url")
        if url:
            image = set_cover_from_url(url)
            if image:
                book.cover.save(*image, save=False)
        book.save()
        return redirect("/book/%s" % book.id)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class ConfirmEditBook(View):
    """confirm edits to a book"""

    def post(self, request, book_id=None):
        """edit a book cool"""
        # returns None if no match is found
        book = models.Edition.objects.filter(id=book_id).first()
        form = forms.EditionForm(request.POST, request.FILES, instance=book)

        data = {"book": book, "form": form}
        if not form.is_valid():
            return TemplateResponse(request, "book/edit_book.html", data)

        with transaction.atomic():
            # save book
            book = form.save()

            # get or create author as needed
            for i in range(int(request.POST.get("author-match-count", 0))):
                match = request.POST.get("author_match-%d" % i)
                if not match:
                    return HttpResponseBadRequest()
                try:
                    # if it's an int, it's an ID
                    match = int(match)
                    author = get_object_or_404(
                        models.Author, id=request.POST["author_match-%d" % i]
                    )
                except ValueError:
                    # otherwise it's a name
                    author = models.Author.objects.create(name=match)
                book.authors.add(author)

            # create work, if needed
            if not book_id:
                work_match = request.POST.get("parent_work")
                if work_match and work_match != "0":
                    work = get_object_or_404(models.Work, id=work_match)
                else:
                    work = models.Work.objects.create(title=form.cleaned_data["title"])
                    work.authors.set(book.authors.all())
                book.parent_work = work
                # we don't tell the world when creating a book
                book.save(broadcast=False)

            for author_id in request.POST.getlist("remove_authors"):
                book.authors.remove(author_id)

        return redirect("/book/%s" % book.id)


class Editions(View):
    """list of editions"""

    def get(self, request, book_id):
        """list of editions of a book"""
        work = get_object_or_404(models.Work, id=book_id)

        if is_api_request(request):
            return ActivitypubResponse(work.to_edition_list(**request.GET))
        filters = {}

        if request.GET.get("language"):
            filters["languages__contains"] = [request.GET.get("language")]
        if request.GET.get("format"):
            filters["physical_format__iexact"] = request.GET.get("format")

        editions = work.editions.order_by("-edition_rank")
        languages = set(sum([e.languages for e in editions], []))

        paginated = Paginator(editions.filter(**filters), PAGE_LENGTH)
        data = {
            "editions": paginated.get_page(request.GET.get("page")),
            "work": work,
            "languages": languages,
            "formats": set(
                e.physical_format.lower() for e in editions if e.physical_format
            ),
        }
        return TemplateResponse(request, "book/editions.html", data)


@login_required
@require_POST
def upload_cover(request, book_id):
    """upload a new cover"""
    book = get_object_or_404(models.Edition, id=book_id)
    book.last_edited_by = request.user

    url = request.POST.get("cover-url")
    if url:
        image = set_cover_from_url(url)
        if image:
            book.cover.save(*image)

        return redirect("{:s}?cover_error=True".format(book.local_path))

    form = forms.CoverForm(request.POST, request.FILES, instance=book)
    if not form.is_valid() or not form.files.get("cover"):
        return redirect(book.local_path)

    book.cover = form.files["cover"]
    book.save()

    return redirect(book.local_path)


def set_cover_from_url(url):
    """load it from a url"""
    try:
        image_file = get_image(url)
    except:  # pylint: disable=bare-except
        return None
    if not image_file:
        return None
    image_name = str(uuid4()) + "." + url.split(".")[-1]
    image_content = ContentFile(image_file.content)
    return [image_name, image_content]


@login_required
@require_POST
@permission_required("bookwyrm.edit_book", raise_exception=True)
def add_description(request, book_id):
    """upload a new cover"""
    if not request.method == "POST":
        return redirect("/")

    book = get_object_or_404(models.Edition, id=book_id)

    description = request.POST.get("description")

    book.description = description
    book.last_edited_by = request.user
    book.save()

    return redirect("/book/%s" % book.id)


@require_POST
def resolve_book(request):
    """figure out the local path to a book from a remote_id"""
    remote_id = request.POST.get("remote_id")
    connector = connector_manager.get_or_create_connector(remote_id)
    book = connector.get_or_create_book(remote_id)

    return redirect("/book/%d" % book.id)


@login_required
@require_POST
@transaction.atomic
def switch_edition(request):
    """switch your copy of a book to a different edition"""
    edition_id = request.POST.get("edition")
    new_edition = get_object_or_404(models.Edition, id=edition_id)
    shelfbooks = models.ShelfBook.objects.filter(
        book__parent_work=new_edition.parent_work, shelf__user=request.user
    )
    for shelfbook in shelfbooks.all():
        with transaction.atomic():
            models.ShelfBook.objects.create(
                created_date=shelfbook.created_date,
                user=shelfbook.user,
                shelf=shelfbook.shelf,
                book=new_edition,
            )
            shelfbook.delete()

    readthroughs = models.ReadThrough.objects.filter(
        book__parent_work=new_edition.parent_work, user=request.user
    )
    for readthrough in readthroughs.all():
        readthrough.book = new_edition
        readthrough.save()

    return redirect("/book/%d" % new_edition.id)
