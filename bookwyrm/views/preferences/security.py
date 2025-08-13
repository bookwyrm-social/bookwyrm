""" class views for 2FA management """
from datetime import datetime, timedelta
from importlib import import_module
import pyotp
import qrcode
import qrcode.image.svg

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.settings import DOMAIN, TWO_FACTOR_LOGIN_MAX_SECONDS
from bookwyrm.views.helpers import set_language

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class UserSecurity(View):
    """change security settings as logged in user"""

    def get(self, request):
        """User Security page"""

        request.user.refresh_user_sessions()

        data = {
            "form": forms.ConfirmPasswordForm(),
            "sessions": request.user.sessions
            if request.user.sessions.count() > 0
            else False,
            "this_session": request.session.session_key,
        }
        return TemplateResponse(request, "preferences/security.html", data)


@login_required
@require_POST
# pylint: disable= unused-argument
def logout_session(request, session_key: str = None):
    """log out session"""

    if session_key:
        # logout the user session
        session = models.UserSession.objects.get(session_key=session_key)
        session.logout()
        # log out the cached session if it still exists
        cache_session = SessionStore()
        if cache_session.exists(session_key=session_key):
            cache_session.delete(session_key=session_key)

    return redirect("/preferences/security")


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Edit2FA(View):
    """change 2FA settings as logged in user"""

    @method_decorator(sensitive_post_parameters("password"))
    def post(self, request):
        """check the user's password"""
        form = forms.ConfirmPasswordForm(request.POST, instance=request.user)
        if not form.is_valid():
            data = {"form": form}
            return TemplateResponse(request, "preferences/security.html", data)
        data = self.create_qr_code(request.user)
        qr_form = forms.Confirm2FAForm()
        data = {
            "password_confirmed": True,
            "qrcode": data[0],
            "code": data[1],
            "form": qr_form,
        }
        return TemplateResponse(request, "preferences/security.html", data)

    def create_qr_code(self, user):
        """generate and save a qr code for 2FA"""
        otp_secret = pyotp.random_base32()
        # save the secret to the user record - we'll need it to check codes in future
        user.otp_secret = otp_secret
        user.save(broadcast=False, update_fields=["otp_secret"])
        # now we create the qr code
        provisioning_url = pyotp.totp.TOTP(otp_secret).provisioning_uri(
            name=user.localname, issuer_name=DOMAIN
        )
        qr_code = qrcode.QRCode(image_factory=qrcode.image.svg.SvgPathImage)
        qr_code.add_data(provisioning_url)
        qr_code.make(fit=True)
        img = qr_code.make_image(attrib={"fill": "black"})
        return [
            str(img.to_string(), "utf-8"),
            otp_secret,
        ]  # to_string() returns a byte string


@method_decorator(login_required, name="dispatch")
class Confirm2FA(View):
    """confirm user's 2FA settings"""

    def post(self, request):
        """confirm the 2FA works before requiring it"""
        form = forms.Confirm2FAForm(request.POST, instance=request.user)

        if not form.is_valid():
            data = {
                "password_confirmed": True,
                "qrcode": Edit2FA.create_qr_code(self, request.user),
                "form": form,
            }
            return TemplateResponse(request, "preferences/security.html", data)

        # set the user's 2FA setting on
        request.user.two_factor_auth = True
        request.user.save(broadcast=False, update_fields=["two_factor_auth"])
        data = {"form": form, "success": True}
        return TemplateResponse(request, "preferences/security.html", data)


@method_decorator(login_required, name="dispatch")
class Disable2FA(View):
    """Turn off 2FA on this user account"""

    def get(self, request):
        """Confirmation page to turn off 2FA"""
        return TemplateResponse(request, "preferences/disable-2fa.html")

    def post(self, request):
        """Turn off 2FA on this user account"""
        request.user.two_factor_auth = False
        request.user.save(broadcast=False, update_fields=["two_factor_auth"])
        data = {"form": forms.ConfirmPasswordForm(), "success": True}
        return TemplateResponse(request, "preferences/security.html", data)


class LoginWith2FA(View):
    """Check 2FA code matches before allowing login"""

    def get(self, request):
        """Display 2FA form"""
        data = {"form": forms.Confirm2FAForm()}
        return TemplateResponse(request, "two_factor_auth/two_factor_login.html", data)

    def post(self, request):
        """Check 2FA code and allow/disallow login"""
        try:
            user = models.User.objects.get(username=request.session.get("2fa_user"))
        except ObjectDoesNotExist:
            request.session["2fa_auth_time"] = 0
            return HttpResponseBadRequest("Invalid user")

        session_time = (
            int(request.session["2fa_auth_time"])
            if request.session["2fa_auth_time"]
            else 0
        )
        elapsed_time = datetime.now() - datetime.fromtimestamp(session_time)
        form = forms.Confirm2FAForm(request.POST, instance=user)
        # don't allow the login credentials to last too long before completing login
        if elapsed_time > timedelta(seconds=TWO_FACTOR_LOGIN_MAX_SECONDS):
            request.session["2fa_user"] = None
            request.session["2fa_auth_time"] = 0
            return redirect("/")
        if not form.is_valid():
            data = {"form": form, "2fa_user": user}
            return TemplateResponse(
                request, "two_factor_auth/two_factor_login.html", data
            )

        # is this a reactivate? let's go for it
        if not user.is_active and user.allow_reactivation:
            user.reactivate()
        # log the user in - we are bypassing standard login
        login(request, user)
        user.update_active_date()

        # record session
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0]
        else:
            ip_address = request.META.get("REMOTE_ADDR", "")
        agent_string = request.META.get("HTTP_USER_AGENT", "")
        models.create_user_session(
            user_id=user.id,
            session_key=request.session.session_key,
            ip_address=ip_address,
            agent_string=agent_string,
        )
        return set_language(user, redirect("/"))


@method_decorator(login_required, name="dispatch")
class GenerateBackupCodes(View):
    """Generate and display backup 2FA codes"""

    def get(self, request):
        """Generate and display backup 2FA codes"""
        data = {"backup_codes": self.generate_backup_codes(request.user)}
        return TemplateResponse(request, "preferences/security.html", data)

    def generate_backup_codes(self, user):
        """generate fresh backup codes for 2FA"""

        # create fresh hotp secrets and count
        hotp_secret = pyotp.random_base32()
        user.hotp_count = 0
        # save the secret to the user record
        user.hotp_secret = hotp_secret
        user.save(broadcast=False, update_fields=["hotp_count", "hotp_secret"])

        # generate codes
        hotp = pyotp.HOTP(hotp_secret)
        counter = 0
        codes = []
        while counter < 10:
            codes.append(hotp.at(counter))
            counter = counter + 1

        return codes


class Prompt2FA(View):
    """Alert user to the existence of 2FA"""

    def get(self, request):
        """Alert user to the existence of 2FA"""
        return TemplateResponse(request, "two_factor_auth/two_factor_prompt.html")
