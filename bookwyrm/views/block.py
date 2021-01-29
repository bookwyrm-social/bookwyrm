''' views for actions you can take in the application '''
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.broadcast import broadcast

# pylint: disable= no-self-use
@method_decorator(login_required, name='dispatch')
class Block(View):
    ''' blocking users '''
    def get(self, request):
        ''' list of blocked users? '''
        return TemplateResponse(
            request, 'preferences/blocks.html', {'title': 'Blocked Users'})

    def post(self, request, user_id):
        ''' block a user '''
        to_block = get_object_or_404(models.User, id=user_id)
        block = models.UserBlocks.objects.create(
            user_subject=request.user, user_object=to_block)
        if not to_block.local:
            broadcast(
                request.user,
                block.to_activity(),
                privacy='direct',
                direct_recipients=[to_block]
            )
        return redirect('/preferences/block')


@require_POST
@login_required
def unblock(request, user_id):
    ''' undo a block '''
    to_unblock = get_object_or_404(models.User, id=user_id)
    try:
        block = models.UserBlocks.objects.get(
            user_subject=request.user,
            user_object=to_unblock,
        )
    except models.UserBlocks.DoesNotExist:
        return HttpResponseNotFound()

    if not to_unblock.local:
        broadcast(
            request.user,
            block.to_undo_activity(request.user),
            privacy='direct',
            direct_recipients=[to_unblock]
        )
    block.delete()
    return redirect('/preferences/block')
