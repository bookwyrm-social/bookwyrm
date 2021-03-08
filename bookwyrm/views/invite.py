""" invites when registration is closed """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.create_invites", raise_exception=True),
    name="dispatch",
)
class ManageInvites(View):
    """ create invites """

    def get(self, request):
        """ invite management page """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        paginated = Paginator(
            models.SiteInvite.objects.filter(user=request.user).order_by(
                "-created_date"
            ),
            PAGE_LENGTH,
        )

        data = {
            "invites": paginated.page(page),
            "form": forms.CreateInviteForm(),
        }
        return TemplateResponse(request, "settings/manage_invites.html", data)

    def post(self, request):
        """ creates an invite database entry """
        form = forms.CreateInviteForm(request.POST)
        if not form.is_valid():
            return HttpResponseBadRequest("ERRORS : %s" % (form.errors,))

        invite = form.save(commit=False)
        invite.user = request.user
        invite.save()

        paginated = Paginator(
            models.SiteInvite.objects.filter(user=request.user).order_by(
                "-created_date"
            ),
            PAGE_LENGTH,
        )
        data = {"invites": paginated.page(1), "form": form}
        return TemplateResponse(request, "settings/manage_invites.html", data)


class Invite(View):
    """ use an invite to register """

    def get(self, request, code):
        """ endpoint for using an invites """
        if request.user.is_authenticated:
            return redirect("/")
        invite = get_object_or_404(models.SiteInvite, code=code)

        data = {
            "register_form": forms.RegisterForm(),
            "invite": invite,
            "valid": invite.valid() if invite else True,
        }
        return TemplateResponse(request, "invite.html", data)

    # post handling is in views.authentication.Register
