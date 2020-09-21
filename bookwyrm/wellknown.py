''' responds to various requests to /.well-know '''
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.http import JsonResponse

from bookwyrm import models
from bookwyrm.settings import DOMAIN


def webfinger(request):
    ''' allow other servers to ask about a user '''
    if request.method != 'GET':
        return HttpResponseNotFound()

    resource = request.GET.get('resource')
    if not resource and not resource.startswith('acct:'):
        return HttpResponseBadRequest()
    ap_id = resource.replace('acct:', '')
    user = models.User.objects.filter(username=ap_id).first()
    if not user:
        return HttpResponseNotFound('No account found')
    return JsonResponse({
        'subject': 'acct:%s' % (user.username),
        'links': [
            {
                'rel': 'self',
                'type': 'application/activity+json',
                'href': user.remote_id
            }
        ]
    })


def nodeinfo_pointer(request):
    ''' direct servers to nodeinfo '''
    if request.method != 'GET':
        return HttpResponseNotFound()

    return JsonResponse({
        'links': [
            {
                'rel': 'http://nodeinfo.diaspora.software/ns/schema/2.0',
                'href': 'https://%s/nodeinfo/2.0' % DOMAIN
            }
        ]
    })


def nodeinfo(request):
    ''' basic info about the server '''
    if request.method != 'GET':
        return HttpResponseNotFound()

    status_count = models.Status.objects.filter(user__local=True).count()
    user_count = models.User.objects.count()
    return JsonResponse({
        'version': '2.0',
        'software': {
            'name': 'bookwyrm',
            'version': '0.0.1'
        },
        'protocols': [
            'activitypub'
        ],
        'usage': {
            'users': {
                'total': user_count,
                'activeMonth': user_count, # TODO
                'activeHalfyear': user_count, # TODO
            },
            'localPosts': status_count,
        },
        'openRegistrations': True,
    })


def instance_info(request):
    ''' what this place is TODO: should be settable/editable '''
    if request.method != 'GET':
        return HttpResponseNotFound()

    user_count = models.User.objects.count()
    status_count = models.Status.objects.count()
    return JsonResponse({
        'uri': DOMAIN,
        'title': 'FediReads',
        'short_description': 'Social reading, decentralized',
        'description': '',
        'email': 'mousereeve@riseup.net',
        'version': '0.0.1',
        'stats': {
            'user_count': user_count,
            'status_count': status_count,
        },
        'thumbnail': '', # TODO: logo thumbnail
        'languages': [
            'en'
        ],
        'registrations': True,
        'approval_required': False,
    })


def peers(request):
    ''' list of federated servers this instance connects with '''
    if request.method != 'GET':
        return HttpResponseNotFound()

    names = models.FederatedServer.objects.values_list('server_name', flat=True)
    return JsonResponse(list(names), safe=False)
