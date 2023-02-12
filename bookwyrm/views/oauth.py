""" invites when registration is closed """
from functools import reduce
import operator
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import emailing, forms, models
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable= no-self-use
class OAuthRegister(View):
    """use an invite to register"""

    def get(self, request):
        if request.user.is_authenticated or 'oauth-newuser' not in request.session:
            return redirect("/")
        data = {
            "register_form": forms.RegisterForm(),
            "username": request.session['oauth-newuser'],
            "valid": True,
        }
        return TemplateResponse(request, "landing/oauth_register.html", data)

    # post handling is in views.register.Register
