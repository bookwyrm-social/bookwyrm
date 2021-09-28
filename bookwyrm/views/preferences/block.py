""" views for actions you can take in the application """
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Block(View):
    """blocking users"""

    def get(self, request):
        """list of blocked users?"""
        return TemplateResponse(request, "preferences/blocks.html")

    def post(self, request, user_id):
        """block a user"""
        to_block = get_object_or_404(models.User, id=user_id)
        models.UserBlocks.objects.create(
            user_subject=request.user, user_object=to_block
        )
        return redirect("prefs-block")


@require_POST
@login_required
def unblock(request, user_id):
    """undo a block"""
    to_unblock = get_object_or_404(models.User, id=user_id)
    block = get_object_or_404(
        models.UserBlocks,
        user_subject=request.user,
        user_object=to_unblock,
    )
    block.delete()
    return redirect("prefs-block")
