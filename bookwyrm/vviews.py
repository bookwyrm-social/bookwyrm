''' views for pages you can go to in the application '''
from django.template.response import TemplateResponse


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
