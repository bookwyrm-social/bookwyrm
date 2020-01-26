''' activitystream api '''
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseNotFound, JsonResponse
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
    ''' helper function to create structured webfinger json '''
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

def inbox(request, username):
    ''' incoming activitypub events '''
    # TODO RSA junk: signature = request.headers['Signature']
    user = User.objects.get(username=username)


def outbox(request, username):
    user = User.objects.get(username=username)
    if request.method == 'GET':
        # list of activities
        return JsonResponse()

    data = request.body.decode('utf-8')
    if data.activity.type == 'Follow':
        handle_follow(data)
    return HttpResponse()

def handle_follow(data):
    pass

def get_or_create_remote_user(activity):
    pass


