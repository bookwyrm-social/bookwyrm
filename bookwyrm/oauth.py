""" responds to various requests to oauth """
from django.contrib.auth import login
from django.core.exceptions import ObjectDoesNotExist
from django.dispatch import receiver
from django.urls import reverse
from django.shortcuts import render, redirect
from django.template.response import TemplateResponse
from authlib.integrations.django_client import OAuth, OAuthError

from bookwyrm import models
from bookwyrm.settings import DOMAIN

oauth = OAuth()
oauth.register('oauth')
oauth = oauth.oauth

def auth(request):
    try:
        token = oauth.authorize_access_token(request)
    except OAuthError:
        data = {}
        return TemplateResponse(request, "landing/login.html", data)
    acct = oauth.get("https://raphus.social/api/v1/accounts/verify_credentials",token=token)
    if (acct.status_code==200):
        localname = dict(acct.json())['acct']
        username = "{}@{}".format(localname,DOMAIN)
        try:
            user = models.User.objects.get(username=username)
        except ObjectDoesNotExist:
            request.session['oauth-newuser'] = localname
            request.session["oauth-newuser-pfp"] = dict(acct.json())['avatar']
            return redirect('oauth-register')
        login(request,user)
    return redirect('/')

def request_login(request):
    redirect_uri = request.build_absolute_uri(reverse('oauth'))
    return oauth.authorize_redirect(request, redirect_uri, force_login=True )
