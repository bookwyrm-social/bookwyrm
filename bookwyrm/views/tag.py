""" tagging views"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from .helpers import is_api_request


# pylint: disable= no-self-use
class Tag(View):
    """ tag page """

    def get(self, request, tag_id):
        """ see books related to a tag """
        tag_obj = get_object_or_404(models.Tag, identifier=tag_id)

        if is_api_request(request):
            return ActivitypubResponse(tag_obj.to_activity(**request.GET))

        books = models.Edition.objects.filter(
            usertag__tag__identifier=tag_id
        ).distinct()
        data = {
            "books": books,
            "tag": tag_obj,
        }
        return TemplateResponse(request, "tag.html", data)


@method_decorator(login_required, name="dispatch")
class AddTag(View):
    """ add a tag to a book """

    def post(self, request):
        """ tag a book """
        # I'm not using a form here because sometimes "name" is sent as a hidden
        # field which doesn't validate
        name = request.POST.get("name")
        book_id = request.POST.get("book")
        book = get_object_or_404(models.Edition, id=book_id)
        tag_obj, _ = models.Tag.objects.get_or_create(
            name=name,
        )
        models.UserTag.objects.get_or_create(
            user=request.user,
            book=book,
            tag=tag_obj,
        )

        return redirect("/book/%s" % book_id)


@method_decorator(login_required, name="dispatch")
class RemoveTag(View):
    """ remove a user's tag from a book """

    def post(self, request):
        """ untag a book """
        name = request.POST.get("name")
        tag_obj = get_object_or_404(models.Tag, name=name)
        book_id = request.POST.get("book")
        book = get_object_or_404(models.Edition, id=book_id)

        user_tag = get_object_or_404(
            models.UserTag, tag=tag_obj, book=book, user=request.user
        )
        user_tag.delete()

        return redirect("/book/%s" % book_id)
