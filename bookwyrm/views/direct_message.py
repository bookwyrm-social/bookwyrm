''' non-interactive pages '''
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm.settings import PAGE_LENGTH
from .helpers import get_activity_feed


# pylint: disable= no-self-use
@method_decorator(login_required, name='dispatch')
class DirectMessage(View):
    ''' dm view '''
    def get(self, request, page=1):
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
