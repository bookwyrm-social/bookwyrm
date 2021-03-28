""" invites when registration is closed """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import emailing, forms, models
from bookwyrm.settings import PAGE_LENGTH
from . import helpers


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


class ManageInviteRequests(View):
    """ grant invites like the benevolent lord you are """

    def get(self, request):
        """ view a list of requests """
        ignored = request.GET.get("ignored", False)
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        paginated = Paginator(
            models.InviteRequest.objects.filter(ignored=ignored).order_by(
                "-created_date"
            ),
            PAGE_LENGTH,
        )

        data = {
            "ignored": ignored,
            "count": paginated.count,
            "requests": paginated.page(page),
        }
        return TemplateResponse(request, "settings/manage_invite_requests.html", data)

    def post(self, request):
        """ send out an invite """
        invite_request = get_object_or_404(
            models.InviteRequest, id=request.POST.get("invite-request")
        )
        # allows re-sending invites
        invite_request.invite, _ = models.SiteInvite.objects.get_or_create(
            use_limit=1,
            user=request.user,
        )

        invite_request.save()
        emailing.invite_email(invite_request)
        return redirect("settings-invite-requests")


class InviteRequest(View):
    """ prospective users sign up here """

    def post(self, request):
        """ create a request """
        form = forms.InviteRequestForm(request.POST)
        received = False
        if form.is_valid():
            received = True
            form.save()

        data = {
            "request_form": form,
            "request_received": received,
            "books": helpers.get_discover_books(),
        }
        return TemplateResponse(request, "discover/discover.html", data)


@require_POST
def ignore_invite_request(request):
    """ hide an invite request """
    invite_request = get_object_or_404(
        models.InviteRequest, id=request.POST.get("invite-request")
    )

    invite_request.ignored = not invite_request.ignored
    invite_request.save()
    return redirect("settings-invite-requests")
