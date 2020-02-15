''' responds to various requests to /.well-know '''
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.http import JsonResponse

from fedireads import models
from fedireads.settings import DOMAIN


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
                'href': user.actor
            }
        ]
    })


def nodeinfo(request):
    ''' idk what this is, but mastodon asked for it '''
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
