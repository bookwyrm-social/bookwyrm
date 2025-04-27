""" the good stuff! the books! """

from re import sub, findall

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views import View

from bookwyrm import book_search, forms, models
from bookwyrm.utils.images import remove_uploaded_image_exif

# from bookwyrm.activitypub.base_activity import ActivityObject
from bookwyrm.utils.isni import (
    find_authors_by_name,
    build_author_from_isni,
    augment_author_metadata,
)
from bookwyrm.views.helpers import get_edition, get_mergeable_object_or_404
from .books import set_cover_from_url


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class EditBook(View):
    """edit a book"""

    def get(self, request, book_id):
        """info about a book"""
        book = get_edition(book_id)
        # This doesn't update the sort title, just pre-populates it in the form
        if book.sort_title in ["", None]:
            book.sort_title = book.guess_sort_title()
        if not book.description:
            book.description = book.parent_work.description
        data = {"book": book, "form": forms.EditionForm(instance=book)}
        return TemplateResponse(request, "book/edit/edit_book.html", data)

    def post(self, request, book_id):
        """edit a book cool"""
        book = get_mergeable_object_or_404(models.Edition, id=book_id)

        form = forms.EditionForm(request.POST, request.FILES, instance=book)

        data = {"book": book, "form": form}
        ensure_transient_values_persist(request, data)
        if not form.is_valid():
            ensure_transient_values_persist(request, data, add_author=True)
            return TemplateResponse(request, "book/edit/edit_book.html", data)

        data = add_authors(request, data)

        # either of the above cases requires additional confirmation
        if data.get("add_author"):
            return TemplateResponse(request, "book/edit/edit_book.html", data)

        remove_authors = request.POST.getlist("remove_authors")
        for author_id in remove_authors:
            book.authors.remove(author_id)

        book = form.save(request, commit=False)

        url = request.POST.get("cover-url")
        if url:
            image = set_cover_from_url(url)
            if image:
                book.cover.save(*image, save=False)
        elif "cover" in form.files:
            book.cover = remove_uploaded_image_exif(form.files["cover"])

        book.save()
        return redirect(f"/book/{book.id}")


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class CreateBook(View):
    """brand new book"""

    def get(self, request):
        """info about a book"""
        data = {"form": forms.EditionForm()}
        return TemplateResponse(request, "book/edit/edit_book.html", data)

    def post(self, request):
        """create a new book"""
        # returns None if no match is found
        form = forms.EditionForm(request.POST, request.FILES)
        data = {"form": form}

        # collect data provided by the work or import item
        parent_work_id = request.POST.get("parent_work")
        authors = None
        if request.POST.get("authors"):
            author_ids = findall(r"\d+", request.POST["authors"])
            authors = models.Author.objects.filter(id__in=author_ids)

        # fake book in case we need to keep editing
        if parent_work_id:
            data["book"] = {
                "parent_work": {"id": parent_work_id},
                "authors": authors,
            }

        if not form.is_valid():
            ensure_transient_values_persist(request, data, form=form)
            return TemplateResponse(request, "book/edit/edit_book.html", data)

        # we have to call this twice because it requires form.cleaned_data
        # which only exists after we validate the form
        ensure_transient_values_persist(request, data, form=form)
        data = add_authors(request, data)

        # check if this is an edition of an existing work
        author_text = ", ".join(data.get("add_author", []))
        data["book_matches"] = book_search.search(
            f'{form.cleaned_data.get("title")} {author_text}',
            min_confidence=0.1,
        )[:5]

        # go to confirm mode
        if not parent_work_id or data.get("add_author"):
            data["confirm_mode"] = True
            return TemplateResponse(request, "book/edit/edit_book.html", data)

        with transaction.atomic():
            book = form.save(request)
            parent_work = get_mergeable_object_or_404(models.Work, id=parent_work_id)
            book.parent_work = parent_work

            if authors:
                book.authors.add(*authors)

            url = request.POST.get("cover-url")
            if url:
                image = set_cover_from_url(url)
                if image:
                    book.cover.save(*image, save=False)
            elif "cover" in form.files:
                book.cover = remove_uploaded_image_exif(form.files["cover"])

            book.save()
        return redirect(f"/book/{book.id}")


def ensure_transient_values_persist(request, data, **kwargs):
    """ensure that values of transient form fields persist when re-rendering the form"""
    data["cover_url"] = request.POST.get("cover-url")
    if kwargs and kwargs.get("form"):
        data["book"] = data.get("book") or {}
        data["book"]["subjects"] = kwargs["form"].cleaned_data["subjects"]
        data["add_author"] = request.POST.getlist("add_author")
    elif kwargs and kwargs.get("add_author") is True:
        data["add_author"] = request.POST.getlist("add_author")


def add_authors(request, data):
    """helper for adding authors"""
    add_author = [author for author in request.POST.getlist("add_author") if author]
    if not add_author:
        data["add_author"] = []
        return data

    data["add_author"] = add_author
    data["author_matches"] = []
    data["isni_matches"] = []

    # creating a book or adding an author to a book needs another step
    data["confirm_mode"] = True
    # this isn't preserved because it isn't part of the form obj
    data["remove_authors"] = request.POST.getlist("remove_authors")

    for author in add_author:
        # filter out empty author fields
        if not author:
            continue
        # check for existing authors
        vector = SearchVector("name", weight="A") + SearchVector("aliases", weight="B")

        author_matches = (
            models.Author.objects.annotate(search=vector)
            .annotate(rank=SearchRank(vector, author, normalization=32))
            .filter(rank__gt=0.4)
            .order_by("-rank")[:5]
        )

        isni_authors = find_authors_by_name(
            author, description=True
        )  # find matches from ISNI API

        # dedupe isni authors we already have in the DB
        exists = [
            i
            for i in isni_authors
            for a in author_matches
            if sub(r"\D", "", str(i.isni)) == sub(r"\D", "", str(a.isni))
        ]

        # pylint: disable=cell-var-from-loop
        matches = list(filter(lambda x: x not in exists, isni_authors))
        # combine existing and isni authors
        matches.extend(author_matches)

        data["author_matches"].append(
            {
                "name": author.strip(),
                "matches": matches,
                "existing_isnis": exists,
            }
        )
    return data


@require_POST
@permission_required("bookwyrm.edit_book", raise_exception=True)
def create_book_from_data(request):
    """create a book with starter data"""
    author_ids = findall(r"\d+", request.POST.get("authors"))
    book = {
        "parent_work": {"id": request.POST.get("parent_work")},
        "authors": models.Author.objects.filter(id__in=author_ids).all(),
        "subjects": request.POST.getlist("subjects"),
    }

    data = {"book": book, "form": forms.EditionForm(request.POST)}
    return TemplateResponse(request, "book/edit/edit_book.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class ConfirmEditBook(View):
    """confirm edits to a book"""

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    def post(self, request, book_id=None):
        """edit a book cool"""
        # returns None if no match is found
        book = models.Edition.objects.filter(id=book_id).first()
        form = forms.EditionForm(request.POST, request.FILES, instance=book)

        data = {"book": book, "form": form}
        if not form.is_valid():
            return TemplateResponse(request, "book/edit/edit_book.html", data)

        with transaction.atomic():
            # save book
            book = form.save(request)

            # add known authors
            authors = None
            if request.POST.get("authors"):
                author_ids = findall(r"\d+", request.POST["authors"])
                authors = models.Author.objects.filter(id__in=author_ids)
                book.authors.add(*authors)

            # get or create author as needed
            for i in range(int(request.POST.get("author-match-count", 0))):
                match = request.POST.get(f"author_match-{i}")
                if not match:
                    return HttpResponseBadRequest()
                try:
                    # if it's an int, it's an ID
                    match = int(match)
                    author = get_object_or_404(
                        models.Author, id=request.POST[f"author_match-{i}"]
                    )
                    # update author metadata if the ISNI record is more complete
                    isni = request.POST.get(f"isni-for-{match}", None)
                    if isni is not None:
                        augment_author_metadata(author, isni)
                except ValueError:
                    # otherwise it's a new author
                    isni_match = request.POST.get(f"author_match-{i}")
                    author_object = build_author_from_isni(isni_match)
                    # with author data class from isni id
                    if "author" in author_object:
                        skeleton = models.Author.objects.create(
                            name=author_object["author"].name
                        )
                        author = author_object["author"].to_model(
                            model=models.Author, overwrite=True, instance=skeleton
                        )
                    else:
                        # or it's just a name
                        author = models.Author.objects.create(name=match)
                book.authors.add(author)

            # create work, if needed
            if not book.parent_work:
                work_match = request.POST.get("parent_work")
                if work_match and work_match != "0":
                    work = get_mergeable_object_or_404(models.Work, id=work_match)
                else:
                    work = models.Work.objects.create(title=form.cleaned_data["title"])
                    work.authors.set(book.authors.all())
                book.parent_work = work

            for author_id in request.POST.getlist("remove_authors"):
                book.authors.remove(author_id)

            # import cover, if requested
            url = request.POST.get("cover-url")
            if url:
                image = set_cover_from_url(url)
                if image:
                    book.cover.save(*image, save=False)
            elif "cover" in form.files:
                book.cover = remove_uploaded_image_exif(form.files["cover"])

            # we don't tell the world when creating a book
            book.save(broadcast=False)

        return redirect(f"/book/{book.id}")
