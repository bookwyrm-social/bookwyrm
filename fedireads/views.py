''' views for pages you can go to in the application '''
import re

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.http import HttpResponseBadRequest, HttpResponseNotFound,\
        JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt

from fedireads import activitypub, outgoing
from fedireads import forms, models, books_manager
from fedireads import goodreads_import
from fedireads.books_manager import get_or_create_book
from fedireads.tasks import app


def get_user_from_username(username):
    ''' helper function to resolve a localname or a username to a user '''
    try:
        user = models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        user = models.User.objects.get(username=username)
    return user


def is_api_request(request):
    ''' check whether a request is asking for html or data '''
    return 'json' in request.headers.get('Accept') or \
            request.path[-5:] == '.json'


def server_error_page(request):
    ''' 500 errors '''
    return TemplateResponse(request, 'error.html')


def not_found_page(request, _):
    ''' 404s '''
    return TemplateResponse(request, 'notfound.html')


@login_required
def home(request):
    ''' this is the same as the feed on the home tab '''
    return home_tab(request, 'home')


@login_required
def home_tab(request, tab):
    ''' user's homepage with activity feed '''
    page_size = 15
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1

    shelves = []
    shelves = get_user_shelf_preview(
        request.user,
        [('reading', 3), ('read', 1), ('to-read', 3)]
    )
    size = sum(len(s['books']) for s in shelves)
    # books new to the instance, for discovery
    if size < 6:
        recent_books = models.Work.objects.order_by(
            '-created_date'
        )[:6 - size]
        recent_books = [b.default_edition for b in recent_books]
        shelves.append({
            'name': 'Recently added',
            'identifier': None,
            'books': recent_books,
            'count': 6 - size,
        })


    # allows us to check if a user has shelved a book
    user_books = models.Edition.objects.filter(shelves__user=request.user).all()

    activities = get_activity_feed(request.user, tab)

    activity_count = activities.count()
    activities = activities[(page - 1) * page_size:page * page_size]

    next_page = '/?page=%d' % (page + 1)
    prev_page = '/?page=%d' % (page - 1)
    data = {
        'user': request.user,
        'shelves': shelves,
        'user_books': user_books,
        'activities': activities,
        'feed_tabs': [
            {'id': 'home', 'display': 'Home'},
            {'id': 'local', 'display': 'Local'},
            {'id': 'federated', 'display': 'Federated'}
        ],
        'active_tab': tab,
        'review_form': forms.ReviewForm(),
        'quotation_form': forms.QuotationForm(),
        'comment_form': forms.CommentForm(),
        'next': next_page if activity_count > (page_size * page) else None,
        'prev': prev_page if page > 1 else None,
    }
    return TemplateResponse(request, 'feed.html', data)


def get_activity_feed(user, filter_level, model=models.Status):
    ''' get a filtered queryset of statuses '''
    # status updates for your follow network
    following = models.User.objects.filter(
        Q(followers=user) | Q(id=user.id)
    )

    activities = model
    if hasattr(model, 'objects'):
        activities = model.objects

    activities = activities.order_by(
        '-created_date'
    )
    if hasattr(activities, 'select_subclasses'):
        activities = activities.select_subclasses()

    # TODO: privacy relationshup between request.user and user
    if filter_level in ['friends', 'home']:
        # people you follow and direct mentions
        activities = activities.filter(
            Q(user__in=following, privacy='public') | \
                Q(mention_users=user)
        )
    elif filter_level == 'self':
        activities = activities.filter(user=user, privacy='public')
    elif filter_level == 'local':
        # everyone on this instance
        activities = activities.filter(user__local=True, privacy='public')
    else:
        # all activities from everyone you federate with
        activities = activities.filter(privacy='public')

    return activities


def search(request):
    ''' that search bar up top '''
    query = request.GET.get('q')
    if re.match(r'\w+@\w+.\w+', query):
        # if something looks like a username, search with webfinger
        results = [outgoing.handle_account_search(query)]
        return TemplateResponse(
            request, 'user_results.html', {'results': results}
        )

    # or just send the question over to book search

    if is_api_request(request):
        # only return local results via json so we don't cause a cascade
        results = books_manager.local_search(query)
        return JsonResponse([r.__dict__ for r in results], safe=False)

    results = books_manager.search(query)
    return TemplateResponse(request, 'book_results.html', {'results': results})


def books_page(request):
    ''' discover books '''
    recent_books = models.Work.objects
    recent_books = recent_books.order_by('-created_date')[:50]
    recent_books = [b.default_edition for b in recent_books]
    if request.user.is_authenticated:
        recent_books = models.Edition.objects.filter(
            ~Q(shelfbook__shelf__user=request.user),
            id__in=[b.id for b in recent_books if b],
        )

    data = {
        'books': recent_books,
    }
    return TemplateResponse(request, 'books.html', data)


@login_required
def import_page(request):
    ''' import history from goodreads '''
    return TemplateResponse(request, 'import.html', {
        'import_form': forms.ImportForm(),
        'jobs': models.ImportJob.
                objects.filter(user=request.user).order_by('-created_date'),
        'limit': goodreads_import.MAX_ENTRIES,
    })


@login_required
def import_status(request, job_id):
    ''' status of an import job '''
    job = models.ImportJob.objects.get(id=job_id)
    if job.user != request.user:
        raise PermissionDenied
    task = app.AsyncResult(job.task_id)
    return TemplateResponse(request, 'import_status.html', {
        'job': job,
        'items': job.items.order_by('index').all(),
        'task': task
    })


def login_page(request):
    ''' authentication '''
    # send user to the login page
    data = {
        'login_form': forms.LoginForm(),
        'register_form': forms.RegisterForm(),
    }
    return TemplateResponse(request, 'login.html', data)


@login_required
def notifications_page(request):
    ''' list notitications '''
    notifications = request.user.notification_set.all() \
            .order_by('-created_date')
    unread = [n.id for n in notifications.filter(read=False)]
    data = {
        'notifications': notifications,
        'unread': unread,
    }
    notifications.update(read=True)
    return TemplateResponse(request, 'notifications.html', data)

@csrf_exempt
def user_page(request, username, subpage=None):
    ''' profile page for a user '''
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    if is_api_request(request):
        # we have a json request
        return JsonResponse(activitypub.get_actor(user))
    # otherwise we're at a UI view

    # TODO: change display with privacy and authentication considerations

    data = {
        'user': user,
        'is_self': request.user.id == user.id,
    }
    if subpage == 'followers':
        data['followers'] = user.followers.all()
        return TemplateResponse(request, 'followers.html', data)
    if subpage == 'following':
        data['following'] = user.following.all()
        return TemplateResponse(request, 'following.html', data)
    if subpage == 'shelves':
        data['shelves'] = user.shelf_set.all()
        return TemplateResponse(request, 'user_shelves.html', data)

    shelves = get_user_shelf_preview(user)
    data['shelves'] = shelves
    activities = get_activity_feed(user, 'self')[:15]
    data['activities'] = activities
    return TemplateResponse(request, 'user.html', data)


@csrf_exempt
def followers_page(request, username):
    ''' list of followers '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    if is_api_request(request):
        user = models.User.objects.get(localname=username)
        followers = user.followers
        page = request.GET.get('page')
        return JsonResponse(activitypub.get_followers(user, page, followers))

    return user_page(request, username, subpage='followers')


@csrf_exempt
def following_page(request, username):
    ''' list of followers '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    if is_api_request(request):
        user = models.User.objects.get(localname=username)
        following = user.following
        page = request.GET.get('page')
        return JsonResponse(activitypub.get_following(user, page, following))

    return user_page(request, username, subpage='following')


@csrf_exempt
def user_shelves_page(request, username):
    ''' list of followers '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    return user_page(request, username, subpage='shelves')


@csrf_exempt
def status_page(request, username, status_id):
    ''' display a particular status (and replies, etc) '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    try:
        user = get_user_from_username(username)
        status = models.Status.objects.select_subclasses().get(id=status_id)
    except ValueError:
        return HttpResponseNotFound()

    if user != status.user:
        return HttpResponseNotFound()

    if is_api_request(request):
        return JsonResponse(status.activitypub_serialize)

    data = {
        'status': status,
    }
    return TemplateResponse(request, 'status.html', data)


@csrf_exempt
def replies_page(request, username, status_id):
    ''' ordered collection of replies to a status '''
    if request.method != 'GET':
        return HttpResponseBadRequest()

    if not is_api_request(request):
        return status_page(request, username, status_id)

    status = models.Status.objects.get(id=status_id)
    if status.user.localname != username:
        return HttpResponseNotFound()

    replies = models.Status.objects.filter(
        reply_parent=status,
    ).select_subclasses()

    if request.GET.get('only_other_accounts'):
        replies = replies.filter(
            ~Q(user=status.user)
        )
    else:
        replies = replies.filter(user=status.user)

    if request.GET.get('page'):
        min_id = request.GET.get('min_id')
        if min_id:
            replies = replies.filter(id__gt=min_id)
        max_id = request.GET.get('max_id')
        if max_id:
            replies = replies.filter(id__lte=max_id)
        activity = activitypub.get_replies_page(status, replies)
        return JsonResponse(activity)

    return JsonResponse(activitypub.get_replies(status, replies))


@login_required
def edit_profile_page(request):
    ''' profile page for a user '''
    user = request.user

    form = forms.EditUserForm(instance=request.user)
    data = {
        'form': form,
        'user': user,
    }
    return TemplateResponse(request, 'edit_user.html', data)


def book_page(request, book_id, tab='friends'):
    ''' info about a book '''
    if ':' in book_id:
        try:
            connector_id, key, book_id = book_id.split(':')
        except ValueError:
            return HttpResponseNotFound()
        book = get_or_create_book(book_id, key=key, connector_id=connector_id)
        return redirect('/book/%d' % book.id)

    book = get_or_create_book(book_id)
    if is_api_request(request):
        return JsonResponse(activitypub.get_book(book))

    if isinstance(book, models.Work):
        book = book.default_edition
    if not book:
        return HttpResponseNotFound()

    work = book.parent_work
    if not work:
        return HttpResponseNotFound()

    book_reviews = models.Review.objects.filter(book__in=work.edition_set.all())

    if request.user.is_authenticated:
        user_reviews = book_reviews.filter(
            user=request.user,
        ).all()

        reviews = get_activity_feed(request.user, tab, model=book_reviews)

        try:
            # TODO: books can be on multiple shelves
            shelf = models.Shelf.objects.filter(
                user=request.user,
                edition=book
            ).first()
        except models.Shelf.DoesNotExist:
            shelf = None

        user_tags = models.Tag.objects.filter(
            book=book, user=request.user
        ).values_list('identifier', flat=True)
    else:
        tab = 'public'
        reviews = book_reviews.filter(privacy='public')
        shelf = None
        user_reviews = []
        user_tags = []

    rating = reviews.aggregate(Avg('rating'))
    tags = models.Tag.objects.filter(
        book=book
    ).values(
        'book', 'name', 'identifier'
    ).distinct().all()

    data = {
        'book': book,
        'shelf': shelf,
        'user_reviews': user_reviews,
        'reviews': reviews.distinct(),
        'rating': rating['rating__avg'],
        'tags': tags,
        'user_tags': user_tags,
        'review_form': forms.ReviewForm(),
        'tag_form': forms.TagForm(),
        'feed_tabs': [
            {'id': 'friends', 'display': 'Friends'},
            {'id': 'local', 'display': 'Local'},
            {'id': 'federated', 'display': 'Federated'}
        ],
        'active_tab': tab,
        'path': '/book/%s' % book_id,
        'cover_form': forms.CoverForm(instance=book),
        'info_fields': [
            {'name': 'ISBN', 'value': book.isbn_13},
            {'name': 'OCLC number', 'value': book.oclc_number},
            {'name': 'OpenLibrary ID', 'value': book.openlibrary_key},
            {'name': 'Goodreads ID', 'value': book.goodreads_key},
            {'name': 'Format', 'value': book.physical_format},
            {'name': 'Pages', 'value': book.pages},
        ],
    }
    return TemplateResponse(request, 'book.html', data)


@login_required
def edit_book_page(request, book_id):
    ''' info about a book '''
    book = get_or_create_book(book_id)
    if not book.description:
        book.description = book.parent_work.description
    data = {
        'book': book,
        'form': forms.EditionForm(instance=book)
    }
    return TemplateResponse(request, 'edit_book.html', data)


def editions_page(request, work_id):
    ''' list of editions of a book '''
    work = models.Work.objects.get(id=work_id)
    editions = models.Edition.objects.filter(parent_work=work).all()
    data = {
        'editions': editions,
        'work': work,
    }
    return TemplateResponse(request, 'editions.html', data)


def author_page(request, author_id):
    ''' landing page for an author '''
    try:
        author = models.Author.objects.get(id=author_id)
    except ValueError:
        return HttpResponseNotFound()

    if is_api_request(request):
        return JsonResponse(activitypub.get_author(author))

    books = models.Work.objects.filter(authors=author)
    data = {
        'author': author,
        'books': [b.default_edition for b in books],
    }
    return TemplateResponse(request, 'author.html', data)


def tag_page(request, tag_id):
    ''' books related to a tag '''
    tag_obj = models.Tag.objects.filter(identifier=tag_id).first()
    books = models.Edition.objects.filter(tag__identifier=tag_id).distinct()
    data = {
        'books': books,
        'tag': tag_obj,
    }
    return TemplateResponse(request, 'tag.html', data)


def shelf_page(request, username, shelf_identifier):
    ''' display a shelf '''
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    shelf = models.Shelf.objects.get(user=user, identifier=shelf_identifier)

    if is_api_request(request):
        return activitypub.get_shelf(shelf)

    data = {
        'shelf': shelf,
        'user': user,
    }
    return TemplateResponse(request, 'shelf.html', data)


def get_user_shelf_preview(user, shelf_proportions=None):
    ''' data for the covers shelf (user page and feed page) '''
    shelves = []
    shelf_max = 6
    if not shelf_proportions:
        shelf_proportions = [('reading', 3), ('read', 2), ('to-read', -1)]
    for (identifier, count) in shelf_proportions:
        if shelf_max <= 0:
            break
        if count > shelf_max or count < 0:
            count = shelf_max

        try:
            shelf = models.Shelf.objects.get(
                user=user,
                identifier=identifier,
            )
        except models.Shelf.DoesNotExist:
            continue

        if not shelf.books.count():
            continue
        books = models.ShelfBook.objects.filter(
            shelf=shelf,
        ).order_by(
            '-updated_date'
        )[:count]

        shelf_max -= len(books)

        shelves.append({
            'name': shelf.name,
            'identifier': shelf.identifier,
            'books': [b.book for b in books],
            'size': shelf.books.count(),
        })
    return shelves
