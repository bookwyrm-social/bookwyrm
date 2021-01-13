''' views for pages you can go to in the application '''
import re

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest
from django.http import HttpResponseNotFound, JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bookwyrm import outgoing
from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.connectors import connector_manager
from bookwyrm.utils import regex

def get_edition(book_id):
    ''' look up a book in the db and return an edition '''
    book = models.Book.objects.select_subclasses().get(id=book_id)
    if isinstance(book, models.Work):
        book = book.get_default_edition()
    return book


def get_user_from_username(username):
    ''' helper function to resolve a localname or a username to a user '''
    # raises DoesNotExist if user is now found
    try:
        return models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return models.User.objects.get(username=username)


def is_api_request(request):
    ''' check whether a request is asking for html or data '''
    return 'json' in request.headers.get('Accept') or \
            request.path[-5:] == '.json'


def server_error_page(request):
    ''' 500 errors '''
    return TemplateResponse(
        request, 'error.html', {'title': 'Oops!'}, status=500)


def not_found_page(request, _):
    ''' 404s '''
    return TemplateResponse(
        request, 'notfound.html', {'title': 'Not found'}, status=404)


@require_GET
def search(request):
    ''' that search bar up top '''
    query = request.GET.get('q')
    min_confidence = request.GET.get('min_confidence', 0.1)

    if is_api_request(request):
        # only return local book results via json so we don't cause a cascade
        book_results = connector_manager.local_search(
            query, min_confidence=min_confidence)
        return JsonResponse([r.json() for r in book_results], safe=False)

    # use webfinger for mastodon style account@domain.com username
    if re.match(r'\B%s' % regex.full_username, query):
        outgoing.handle_remote_webfinger(query)

    # do a local user search
    user_results = models.User.objects.annotate(
        similarity=Greatest(
            TrigramSimilarity('username', query),
            TrigramSimilarity('localname', query),
        )
    ).filter(
        similarity__gt=0.5,
    ).order_by('-similarity')[:10]

    book_results = connector_manager.search(
        query, min_confidence=min_confidence)
    data = {
        'title': 'Search Results',
        'book_results': book_results,
        'user_results': user_results,
        'query': query,
    }
    return TemplateResponse(request, 'search_results.html', data)


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
        return ActivitypubResponse(shelf.to_activity(**request.GET))

    books = models.ShelfBook.objects.filter(
        added_by=user, shelf=shelf
    ).order_by('-updated_date').all()

    data = {
        'title': '%s\'s %s shelf' % (user.display_name, shelf.name),
        'user': user,
        'is_self': is_self,
        'shelves': shelves.all(),
        'shelf': shelf,
        'books': [b.book for b in books],
    }

    return TemplateResponse(request, 'shelf.html', data)
