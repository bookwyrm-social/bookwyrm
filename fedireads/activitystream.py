''' activitystream api '''
from django.http import HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from fedireads.settings import DOMAIN
from fedireads.models import User

def webfinger(request):
    ''' allow other servers to ask about a user '''
    resource = request.GET.get('resource')
    if not resource and not resource.startswith('acct:'):
        return HttpResponseBadRequest()
    account = resource.replace('acct:', '')
    account = account.replace('@' + DOMAIN, '')
    user = User.objects.filter(username=account).first()
    if not user:
        return HttpResponseNotFound('No account found')
    return JsonResponse(format_webfinger(user))

def format_webfinger(user):
    return {
        'subject': 'acct:%s@%s' % (user.username, DOMAIN),
        'links': [
            {
                'rel': 'self',
                'type': 'application/activity+json',
                'href': 'https://%s/user/%s' % (DOMAIN, user.username),
            }
        ]
    }
