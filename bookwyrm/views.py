''' views for pages you can go to in the application '''
import re

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.postgres.search import TrigramSimilarity
from django.core.paginator import Paginator
from django.db.models import Avg, Q
from django.http import HttpResponseNotFound, JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bookwyrm import outgoing
from bookwyrm.activitypub import ActivityEncoder
from bookwyrm import forms, models, books_manager
from bookwyrm import goodreads_import
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.tasks import app
from bookwyrm.utils import regex


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
    return TemplateResponse(request, 'error.html', {'title': 'Oops!'})


def not_found_page(request, _):
    ''' 404s '''
    return TemplateResponse(request, 'notfound.html', {'title': 'Not found'})


@login_required
@require_GET
def home(request):
    ''' this is the same as the feed on the home tab '''
    return home_tab(request, 'home')


@login_required
@require_GET
def home_tab(request, tab):
    ''' user's homepage with activity feed '''
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1

    suggested_books = get_suggested_books(request.user)

    activities = get_activity_feed(request.user, tab)
    paginated = Paginator(activities, PAGE_LENGTH)
    activity_page = paginated.page(page)

    prev_page = next_page = None
    if activity_page.has_next():
        next_page = '/%s/?page=%d#feed' % \
                (tab, activity_page.next_page_number())
    if activity_page.has_previous():
        prev_page = '/%s/?page=%d#feed' % \
                (tab, activity_page.previous_page_number())
    data = {
        'title': 'Updates Feed',
        'user': request.user,
        'suggested_books': suggested_books,
        'activities': activity_page.object_list,
        'tab': tab,
        'next': next_page,
        'prev': prev_page,
    }
    return TemplateResponse(request, 'feed.html', data)


def get_suggested_books(user, max_books=5):
    ''' helper to get a user's recent books '''
    book_count = 0
    preset_shelves = [
        ('reading', max_books), ('read', 2), ('to-read', max_books)
    ]
    suggested_books = []
    for (preset, shelf_max) in preset_shelves:
        limit = shelf_max if shelf_max < (max_books - book_count) \
                else max_books - book_count
        shelf = user.shelf_set.get(identifier=preset)

        shelf_books = shelf.shelfbook_set.order_by(
            '-updated_date'
        ).all()[:limit]
        if not shelf_books:
            continue
        shelf_preview = {
            'name': shelf.name,
            'books': [s.book for s in shelf_books]
        }
        suggested_books.append(shelf_preview)
        book_count += len(shelf_preview['books'])
    return suggested_books


@login_required
@require_GET
def direct_messages_page(request, page=1):
    ''' like a feed but for dms only '''
    activities = get_activity_feed(request.user, 'direct')
    paginated = Paginator(activities, PAGE_LENGTH)
    activity_page = paginated.page(page)

    prev_page = next_page = None
    if activity_page.has_next():
        next_page = '/direct-message/?page=%d#feed' % \
                activity_page.next_page_number()
    if activity_page.has_previous():
        prev_page = '/direct-messages/?page=%d#feed' % \
                activity_page.previous_page_number()
    data = {
        'title': 'Direct Messages',
        'user': request.user,
        'activities': activity_page.object_list,
        'next': next_page,
        'prev': prev_page,
    }
    return TemplateResponse(request, 'direct_messages.html', data)


def get_activity_feed(user, filter_level, model=models.Status):
    ''' get a filtered queryset of statuses '''
    if user.is_anonymous:
        user = None

    if user:
        following = models.User.objects.filter(
            Q(followers=user) | Q(id=user.id)
        )
    else:
        following = []

    activities = model
    if hasattr(model, 'objects'):
        activities = model.objects

    activities = activities.filter(
        deleted=False,
    ).order_by(
        '-published_date'
    )

    if filter_level == 'direct':
        return activities.filter(
            Q(user=user) | Q(mention_users=user),
            privacy='direct'
        )

    # never show DMs in the regular feed
    activities = activities.filter(~Q(privacy='direct'))


    if hasattr(activities, 'select_subclasses'):
        activities = activities.select_subclasses()

    if filter_level in ['friends', 'home']:
        # people you follow and direct mentions
        activities = activities.filter(
            Q(user__in=following, privacy__in=[
                'public', 'unlisted', 'followers'
            ]) | Q(mention_users=user) | Q(user=user)
        )
    elif filter_level == 'self':
        activities = activities.filter(user=user, privacy='public')
    elif filter_level == 'local':
        # everyone on this instance except unlisted
        activities = activities.filter(
            Q(user__in=following, privacy='followers') | Q(privacy='public'),
            user__local=True
        )
    else:
        # all activities from everyone you federate with
        activities = activities.filter(
            Q(user__in=following, privacy='followers') | Q(privacy='public')
        )

    try:
        activities = activities.filter(~Q(boosters__in=activities))
    except ValueError:
        pass

    return activities


@require_GET
def search(request):
    ''' that search bar up top '''
    query = request.GET.get('q')

    if is_api_request(request):
        # only return local book results via json so we don't cause a cascade
        book_results = books_manager.local_search(query)
        return JsonResponse([r.__dict__ for r in book_results], safe=False)

    # use webfinger for mastodon style account@domain.com username
    if re.match(regex.full_username, query):
        outgoing.handle_remote_webfinger(query)

    # do a local user search
    user_results = models.User.objects.annotate(
        similarity=TrigramSimilarity('username', query),
    ).filter(
        similarity__gt=0.5,
    ).order_by('-similarity')[:10]

    book_results = books_manager.search(query)
    data = {
        'title': 'Search Results',
        'book_results': book_results,
        'user_results': user_results,
        'query': query,
    }
    return TemplateResponse(request, 'search_results.html', data)


@login_required
@require_GET
def import_page(request):
    ''' import history from goodreads '''
    return TemplateResponse(request, 'import.html', {
        'title': 'Import Books',
        'import_form': forms.ImportForm(),
        'jobs': models.ImportJob.
                objects.filter(user=request.user).order_by('-created_date'),
        'limit': goodreads_import.MAX_ENTRIES,
    })


@login_required
@require_GET
def import_status(request, job_id):
    ''' status of an import job '''
    job = models.ImportJob.objects.get(id=job_id)
    if job.user != request.user:
        raise PermissionDenied
    task = app.AsyncResult(job.task_id)
    items = job.items.order_by('index').all()
    failed_items = [i for i in items if i.fail_reason]
    items = [i for i in items if not i.fail_reason]
    return TemplateResponse(request, 'import_status.html', {
        'title': 'Import Status',
        'job': job,
        'items': items,
        'failed_items': failed_items,
        'task': task
    })


@require_GET
def login_page(request):
    ''' authentication '''
    if request.user.is_authenticated:
        return redirect('/')
    # send user to the login page
    data = {
        'title': 'Login',
        'login_form': forms.LoginForm(),
        'register_form': forms.RegisterForm(),
    }
    return TemplateResponse(request, 'login.html', data)


@require_GET
def about_page(request):
    ''' more information about the instance '''
    data = {
        'title': 'About',
    }
    return TemplateResponse(request, 'about.html', data)


@require_GET
def password_reset_request(request):
    ''' invite management page '''
    return TemplateResponse(
        request,
        'password_reset_request.html',
        {'title': 'Reset Password'}
    )


@require_GET
def password_reset(request, code):
    ''' endpoint for sending invites '''
    if request.user.is_authenticated:
        return redirect('/')
    try:
        reset_code = models.PasswordReset.objects.get(code=code)
        if not reset_code.valid():
            raise PermissionDenied
    except models.PasswordReset.DoesNotExist:
        raise PermissionDenied

    return TemplateResponse(
        request,
        'password_reset.html',
        {'title': 'Reset Password', 'code': reset_code.code}
    )


@require_GET
def invite_page(request, code):
    ''' endpoint for sending invites '''
    if request.user.is_authenticated:
        return redirect('/')
    try:
        invite = models.SiteInvite.objects.get(code=code)
        if not invite.valid():
            raise PermissionDenied
    except models.SiteInvite.DoesNotExist:
        raise PermissionDenied

    data = {
        'title': 'Join',
        'register_form': forms.RegisterForm(),
        'invite': invite,
    }
    return TemplateResponse(request, 'invite.html', data)


@login_required
@permission_required('bookwyrm.create_invites', raise_exception=True)
@require_GET
def manage_invites(request):
    ''' invite management page '''
    data = {
        'title': 'Invitations',
        'invites': models.SiteInvite.objects.filter(user=request.user),
        'form': forms.CreateInviteForm(),
    }
    return TemplateResponse(request, 'manage_invites.html', data)


@login_required
@require_GET
def notifications_page(request):
    ''' list notitications '''
    notifications = request.user.notification_set.all() \
            .order_by('-created_date')
    unread = [n.id for n in notifications.filter(read=False)]
    data = {
        'title': 'Notifications',
        'notifications': notifications,
        'unread': unread,
    }
    notifications.update(read=True)
    return TemplateResponse(request, 'notifications.html', data)


@csrf_exempt
@require_GET
def user_page(request, username):
    ''' profile page for a user '''
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    if is_api_request(request):
        # we have a json request
        return JsonResponse(user.to_activity(), encoder=ActivityEncoder)
    # otherwise we're at a UI view

    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1

    shelf_preview = []

    # only show other shelves that should be visible
    shelves = user.shelf_set
    is_self = request.user.id == user.id
    if not is_self:
        follower = user.followers.filter(id=request.user.id).exists()
        if follower:
            shelves = shelves.filter(privacy__in=['public', 'followers'])
        else:
            shelves = shelves.filter(privacy='public')

    for user_shelf in shelves.all():
        if not user_shelf.books.count():
            continue
        shelf_preview.append({
            'name': user_shelf.name,
            'remote_id': user_shelf.remote_id,
            'books': user_shelf.books.all()[:3],
            'size': user_shelf.books.count(),
        })
        if len(shelf_preview) > 2:
            break

    # user's posts
    activities = get_activity_feed(user, 'self')
    paginated = Paginator(activities, PAGE_LENGTH)
    activity_page = paginated.page(page)

    prev_page = next_page = None
    if activity_page.has_next():
        next_page = '/user/%s/?page=%d' % \
                (username, activity_page.next_page_number())
    if activity_page.has_previous():
        prev_page = '/user/%s/?page=%d' % \
                (username, activity_page.previous_page_number())
    data = {
        'title': user.name,
        'user': user,
        'is_self': is_self,
        'shelves': shelf_preview,
        'shelf_count': shelves.count(),
        'activities': activity_page.object_list,
        'next': next_page,
        'prev': prev_page,
    }

    return TemplateResponse(request, 'user.html', data)


@csrf_exempt
@require_GET
def followers_page(request, username):
    ''' list of followers '''
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    if is_api_request(request):
        return JsonResponse(user.to_followers_activity(**request.GET))

    data = {
        'title': '%s: followers' % user.name,
        'user': user,
        'is_self': request.user.id == user.id,
        'followers': user.followers.all(),
    }
    return TemplateResponse(request, 'followers.html', data)


@csrf_exempt
@require_GET
def following_page(request, username):
    ''' list of followers '''
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    if is_api_request(request):
        return JsonResponse(user.to_following_activity(**request.GET))

    data = {
        'title': '%s: following' % user.name,
        'user': user,
        'is_self': request.user.id == user.id,
        'following': user.following.all(),
    }
    return TemplateResponse(request, 'following.html', data)


@csrf_exempt
@require_GET
def status_page(request, username, status_id):
    ''' display a particular status (and replies, etc) '''
    try:
        user = get_user_from_username(username)
        status = models.Status.objects.select_subclasses().get(id=status_id)
    except ValueError:
        return HttpResponseNotFound()

    # the url should have the poster's username in it
    if user != status.user:
        return HttpResponseNotFound()

    # make sure the user is authorized to see the status
    if not status_visible_to_user(request.user, status):
        return HttpResponseNotFound()

    if is_api_request(request):
        return JsonResponse(status.to_activity(), encoder=ActivityEncoder)

    data = {
        'title': 'Status by %s' % user.username,
        'status': status,
    }
    return TemplateResponse(request, 'status.html', data)


def status_visible_to_user(viewer, status):
    ''' is a user authorized to view a status? '''
    if viewer == status.user or status.privacy in ['public', 'unlisted']:
        return True
    if status.privacy == 'followers' and \
            status.user.followers.filter(id=viewer.id).first():
        return True
    if status.privacy == 'direct' and \
            status.mention_users.filter(id=viewer.id).first():
        return True
    return False


@csrf_exempt
@require_GET
def replies_page(request, username, status_id):
    ''' ordered collection of replies to a status '''
    if not is_api_request(request):
        return status_page(request, username, status_id)

    status = models.Status.objects.get(id=status_id)
    if status.user.localname != username:
        return HttpResponseNotFound()

    return JsonResponse(
        status.to_replies(**request.GET),
        encoder=ActivityEncoder
    )


@login_required
@require_GET
def edit_profile_page(request):
    ''' profile page for a user '''
    user = request.user

    form = forms.EditUserForm(instance=request.user)
    data = {
        'title': 'Edit profile',
        'form': form,
        'user': user,
    }
    return TemplateResponse(request, 'edit_user.html', data)


@require_GET
def book_page(request, book_id):
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
        return JsonResponse(book.to_activity(), encoder=ActivityEncoder)

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
    reviews = get_activity_feed(request.user, 'federated', model=reviews)

    # the reviews to show
    paginated = Paginator(reviews.filter(content__isnull=False), PAGE_LENGTH)
    reviews_page = paginated.page(page)

    prev_page = next_page = None
    if reviews_page.has_next():
        next_page = '/book/%d/?page=%d' % \
                (book_id, reviews_page.next_page_number())
    if reviews_page.has_previous():
        prev_page = '/book/%s/?page=%d' % \
                (book_id, reviews_page.previous_page_number())

    user_tags = readthroughs = user_shelves = other_edition_shelves = []
    if request.user.is_authenticated:
        user_tags = models.UserTag.objects.filter(
            book=book, user=request.user
        ).values_list('tag__identifier', flat=True)

        readthroughs = models.ReadThrough.objects.filter(
            user=request.user,
            book=book,
        ).order_by('start_date')

        user_shelves = models.ShelfBook.objects.filter(
            added_by=request.user, book=book
        )

        other_edition_shelves = models.ShelfBook.objects.filter(
            ~Q(book=book),
            added_by=request.user,
            book__parent_work=book.parent_work,
        )

    rating = reviews.aggregate(Avg('rating'))
    tags = models.UserTag.objects.filter(
        book=book,
    )

    data = {
        'title': book.title,
        'book': book,
        'reviews': reviews_page,
        'ratings': reviews.filter(content__isnull=True),
        'rating': rating['rating__avg'],
        'tags': tags,
        'user_tags': user_tags,
        'user_shelves': user_shelves,
        'other_edition_shelves': other_edition_shelves,
        'readthroughs': readthroughs,
        'path': '/book/%s' % book_id,
        'info_fields': [
            {'name': 'ISBN', 'value': book.isbn_13},
            {'name': 'OCLC number', 'value': book.oclc_number},
            {'name': 'OpenLibrary ID', 'value': book.openlibrary_key},
            {'name': 'Goodreads ID', 'value': book.goodreads_key},
            {'name': 'Format', 'value': book.physical_format},
            {'name': 'Pages', 'value': book.pages},
        ],
        'next': next_page,
        'prev': prev_page,
    }
    return TemplateResponse(request, 'book.html', data)


@login_required
@permission_required('bookwyrm.edit_book', raise_exception=True)
@require_GET
def edit_book_page(request, book_id):
    ''' info about a book '''
    book = books_manager.get_edition(book_id)
    if not book.description:
        book.description = book.parent_work.description
    data = {
        'title': 'Edit Book',
        'book': book,
        'form': forms.EditionForm(instance=book)
    }
    return TemplateResponse(request, 'edit_book.html', data)


@require_GET
def editions_page(request, book_id):
    ''' list of editions of a book '''
    work = get_object_or_404(models.Work, id=book_id)

    if is_api_request(request):
        return JsonResponse(
            work.to_edition_list(**request.GET),
            encoder=ActivityEncoder
        )

    data = {
        'title': 'Editions of %s' % work.title,
        'editions': work.editions.all(),
        'work': work,
    }
    return TemplateResponse(request, 'editions.html', data)


@require_GET
def author_page(request, author_id):
    ''' landing page for an author '''
    author = get_object_or_404(models.Author, id=author_id)

    if is_api_request(request):
        return JsonResponse(author.to_activity(), encoder=ActivityEncoder)

    books = models.Work.objects.filter(authors=author)
    data = {
        'title': author.name,
        'author': author,
        'books': [b.get_default_edition() for b in books],
    }
    return TemplateResponse(request, 'author.html', data)


@require_GET
def tag_page(request, tag_id):
    ''' books related to a tag '''
    tag_obj = models.Tag.objects.filter(identifier=tag_id).first()
    if not tag_obj:
        return HttpResponseNotFound()

    if is_api_request(request):
        return JsonResponse(
            tag_obj.to_activity(**request.GET), encoder=ActivityEncoder)

    books = models.Edition.objects.filter(
        usertag__tag__identifier=tag_id
    ).distinct()
    data = {
        'title': tag_obj.name,
        'books': books,
        'tag': tag_obj,
    }
    return TemplateResponse(request, 'tag.html', data)


@csrf_exempt
@require_GET
def user_shelves_page(request, username):
    ''' list of followers '''
    return shelf_page(request, username, None)


@require_GET
def shelf_page(request, username, shelf_identifier):
    ''' display a shelf '''
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    if shelf_identifier:
        shelf = user.shelf_set.get(identifier=shelf_identifier)
    else:
        shelf = user.shelf_set.first()

    is_self = request.user == user

    shelves = user.shelf_set
    if not is_self:
        follower = user.followers.filter(id=request.user.id).exists()
        # make sure the user has permission to view the shelf
        if shelf.privacy == 'direct' or \
                (shelf.privacy == 'followers' and not follower):
            return HttpResponseNotFound()

        # only show other shelves that should be visible
        if follower:
            shelves = shelves.filter(privacy__in=['public', 'followers'])
        else:
            shelves = shelves.filter(privacy='public')


    if is_api_request(request):
        return JsonResponse(shelf.to_activity(**request.GET))

    data = {
        'title': user.name,
        'user': user,
        'is_self': is_self,
        'shelves': shelves.all(),
        'shelf': shelf,
    }

    return TemplateResponse(request, 'shelf.html', data)
