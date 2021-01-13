''' views for pages you can go to in the application '''
import re

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET

from bookwyrm import outgoing
from bookwyrm import models
from bookwyrm.connectors import connector_manager
from bookwyrm.utils import regex


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
