''' the good stuff! the books! '''
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import Avg, Q
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.connectors import connector_manager
from bookwyrm.settings import PAGE_LENGTH
from .helpers import is_api_request, get_activity_feed, get_edition
from .helpers import privacy_filter


# pylint: disable= no-self-use
class Book(View):
    ''' a book! this is the stuff '''
    def get(self, request, book_id):
        ''' info about a book '''
        try:
            page = int(request.GET.get('page', 1))
        except ValueError:
            page = 1

        try:
            book = models.Book.objects.select_subclasses().get(id=book_id)
        except models.Book.DoesNotExist:
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(book.to_activity())

        if isinstance(book, models.Work):
            book = book.get_default_edition()
        if not book:
            return HttpResponseNotFound()

        work = book.parent_work
        if not work:
            return HttpResponseNotFound()

        reviews = models.Review.objects.filter(
            book__in=work.editions.all(),
        )
        # all reviews for the book
        reviews = get_activity_feed(
            request.user,
            ['public', 'unlisted', 'followers', 'direct'],
            queryset=reviews
        )

        # the reviews to show
        paginated = Paginator(reviews.exclude(
            Q(content__isnull=True) | Q(content='')
        ), PAGE_LENGTH)
        reviews_page = paginated.page(page)

        user_tags = readthroughs = user_shelves = other_edition_shelves = []
        if request.user.is_authenticated:
            user_tags = models.UserTag.objects.filter(
                book=book, user=request.user
            ).values_list('tag__identifier', flat=True)

            readthroughs = models.ReadThrough.objects.filter(
                user=request.user,
                book=book,
            ).order_by('start_date')

            for readthrough in readthroughs:
                readthrough.progress_updates = \
                    readthrough.progressupdate_set.all() \
                    .order_by('-updated_date')

            user_shelves = models.ShelfBook.objects.filter(
                user=request.user, book=book
            )

            other_edition_shelves = models.ShelfBook.objects.filter(
                ~Q(book=book),
                user=request.user,
                book__parent_work=book.parent_work,
            )

        data = {
            'title': book.title,
            'book': book,
            'reviews': reviews_page,
            'review_count': reviews.count(),
            'ratings': reviews.filter(Q(content__isnull=True) | Q(content='')),
            'rating': reviews.aggregate(Avg('rating'))['rating__avg'],
            'tags':  models.UserTag.objects.filter(book=book),
            'lists': privacy_filter(
                request.user, book.list_set.all()
            ),
            'user_tags': user_tags,
            'user_shelves': user_shelves,
            'other_edition_shelves': other_edition_shelves,
            'readthroughs': readthroughs,
            'path': '/book/%s' % book_id,
        }
        return TemplateResponse(request, 'book.html', data)


@method_decorator(login_required, name='dispatch')
@method_decorator(
    permission_required('bookwyrm.edit_book', raise_exception=True),
    name='dispatch')
class EditBook(View):
    ''' edit a book '''
    def get(self, request, book_id):
        ''' info about a book '''
        book = get_edition(book_id)
        if not book.description:
            book.description = book.parent_work.description
        data = {
            'title': 'Edit Book',
            'book': book,
            'form': forms.EditionForm(instance=book)
        }
        return TemplateResponse(request, 'edit_book.html', data)

    def post(self, request, book_id):
        ''' edit a book cool '''
        book = get_object_or_404(models.Edition, id=book_id)

        form = forms.EditionForm(request.POST, request.FILES, instance=book)
        if not form.is_valid():
            data = {
                'title': 'Edit Book',
                'book': book,
                'form': form
            }
            return TemplateResponse(request, 'edit_book.html', data)
        book = form.save()

        return redirect('/book/%s' % book.id)


class Editions(View):
    ''' list of editions '''
    def get(self, request, book_id):
        ''' list of editions of a book '''
        work = get_object_or_404(models.Work, id=book_id)

        if is_api_request(request):
            return ActivitypubResponse(work.to_edition_list(**request.GET))

        data = {
            'title': 'Editions of %s' % work.title,
            'editions': work.editions.order_by('-edition_rank').all(),
            'work': work,
        }
        return TemplateResponse(request, 'editions.html', data)


@login_required
@require_POST
def upload_cover(request, book_id):
    ''' upload a new cover '''
    book = get_object_or_404(models.Edition, id=book_id)

    form = forms.CoverForm(request.POST, request.FILES, instance=book)
    if not form.is_valid():
        return redirect('/book/%d' % book.id)

    book.cover = form.files['cover']
    book.save()

    return redirect('/book/%s' % book.id)


@login_required
@require_POST
@permission_required('bookwyrm.edit_book', raise_exception=True)
def add_description(request, book_id):
    ''' upload a new cover '''
    if not request.method == 'POST':
        return redirect('/')

    book = get_object_or_404(models.Edition, id=book_id)

    description = request.POST.get('description')

    book.description = description
    book.save()

    return redirect('/book/%s' % book.id)


@require_POST
def resolve_book(request):
    ''' figure out the local path to a book from a remote_id '''
    remote_id = request.POST.get('remote_id')
    connector = connector_manager.get_or_create_connector(remote_id)
    book = connector.get_or_create_book(remote_id)

    return redirect('/book/%d' % book.id)


@login_required
@require_POST
@transaction.atomic
def switch_edition(request):
    ''' switch your copy of a book to a different edition '''
    edition_id = request.POST.get('edition')
    new_edition = get_object_or_404(models.Edition, id=edition_id)
    shelfbooks = models.ShelfBook.objects.filter(
        book__parent_work=new_edition.parent_work,
        shelf__user=request.user
    )
    for shelfbook in shelfbooks.all():
        with transaction.atomic():
            models.ShelfBook.objects.create(
                created_date=shelfbook.created_date,
                user=shelfbook.user,
                shelf=shelfbook.shelf,
                book=new_edition
            )
            shelfbook.delete()

    readthroughs = models.ReadThrough.objects.filter(
        book__parent_work=new_edition.parent_work,
        user=request.user
    )
    for readthrough in readthroughs.all():
        readthrough.book = new_edition
        readthrough.save()

    return redirect('/book/%d' % new_edition.id)
