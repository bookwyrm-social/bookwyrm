''' endpoints for getting updates about activity '''
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View

# pylint: disable= no-self-use
@method_decorator(login_required, name='dispatch')
class Updates(View):
    ''' so the app can poll '''
    def get(self, request):
        ''' any notifications waiting? '''
        return JsonResponse({
            'notifications': request.user.notification_set.filter(
                read=False
            ).count(),
        })
