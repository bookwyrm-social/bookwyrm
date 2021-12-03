""" the good stuff! the books! """
from re import sub
from dateutil.parser import parse as dateparse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import book_search, forms, models

# from bookwyrm.activitypub.base_activity import ActivityObject
from bookwyrm.utils.isni import (
    find_authors_by_name,
    build_author_from_isni,
    augment_author_metadata,
)
from bookwyrm.views.helpers import get_edition
from .books import set_cover_from_url

# pylint: disable=no-self-use
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
        return TemplateResponse(request, "book/edit/edit_book.html", data)

    # pylint: disable=too-many-locals
    def post(self, request, book_id=None):
        """edit a book cool"""
        # returns None if no match is found
        book = models.Edition.objects.filter(id=book_id).first()
        form = forms.EditionForm(request.POST, request.FILES, instance=book)

        data = {"book": book, "form": form}
        if not form.is_valid():
            return TemplateResponse(request, "book/edit/edit_book.html", data)

        # filter out empty author fields
        add_author = [author for author in request.POST.getlist("add_author") if author]
        if add_author:
            data["add_author"] = add_author
            data["author_matches"] = []
            data["isni_matches"] = []

            for author in add_author:
                if not author:
                    continue
                # check for existing authors
                vector = SearchVector("name", weight="A") + SearchVector(
                    "aliases", weight="B"
                )

                author_matches = (
                    models.Author.objects.annotate(search=vector)
                    .annotate(rank=SearchRank(vector, author))
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

        # we're creating a new book
        if not book:
            # check if this is an edition of an existing work
            author_text = book.author_text if book else add_author
            data["book_matches"] = book_search.search(
                f'{form.cleaned_data.get("title")} {author_text}',
                min_confidence=0.5,
            )[:5]

        # either of the above cases requires additional confirmation
        if add_author or not book:
            # creting a book or adding an author to a book needs another step
            data["confirm_mode"] = True
            # this isn't preserved because it isn't part of the form obj
            data["remove_authors"] = request.POST.getlist("remove_authors")
            data["cover_url"] = request.POST.get("cover-url")

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
            return TemplateResponse(request, "book/edit/edit_book.html", data)

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
        return redirect(f"/book/{book.id}")


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
            book = form.save()

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
            if not book_id:
                work_match = request.POST.get("parent_work")
                if work_match and work_match != "0":
                    work = get_object_or_404(models.Work, id=work_match)
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

            # we don't tell the world when creating a book
            book.save(broadcast=False)

        return redirect(f"/book/{book.id}")
