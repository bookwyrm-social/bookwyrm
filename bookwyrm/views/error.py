''' something has gone amiss '''
from django.template.response import TemplateResponse

def server_error_page(request):
    ''' 500 errors '''
    return TemplateResponse(
        request, 'error.html', {'title': 'Oops!'}, status=500)


def not_found_page(request, _):
    ''' 404s '''
    return TemplateResponse(
        request, 'notfound.html', {'title': 'Not found'}, status=404)
