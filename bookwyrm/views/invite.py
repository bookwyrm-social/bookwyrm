''' invites when registration is closed '''
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models


# pylint: disable= no-self-use
@method_decorator(login_required, name='dispatch')
@method_decorator(
    permission_required('bookwyrm.create_invites', raise_exception=True),
    name='dispatch')
class ManageInvites(View):
    ''' create invites '''
    def get(self, request):
        ''' invite management page '''
        data = {
            'title': 'Invitations',
            'invites': models.SiteInvite.objects.filter(
                user=request.user).order_by('-created_date'),
            'form': forms.CreateInviteForm(),
        }
        return TemplateResponse(request, 'manage_invites.html', data)

    def post(self, request):
        ''' creates an invite database entry '''
        form = forms.CreateInviteForm(request.POST)
        if not form.is_valid():
            return HttpResponseBadRequest("ERRORS : %s" % (form.errors,))

        invite = form.save(commit=False)
        invite.user = request.user
        invite.save()

        return redirect('/invite')


class Invite(View):
    ''' use an invite to register '''
    def get(self, request, code):
        ''' endpoint for using an invites '''
        if request.user.is_authenticated:
            return redirect('/')
        invite = get_object_or_404(models.SiteInvite, code=code)

        data = {
            'title': 'Join',
            'register_form': forms.RegisterForm(),
            'invite': invite,
            'valid': invite.valid() if invite else True,
        }
        return TemplateResponse(request, 'invite.html', data)

    # post handling is in views.authentication.Register
