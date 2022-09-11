""" class views for 2FA management """
import pyotp
import qrcode
import qrcode.image.svg
import time

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.debug import sensitive_post_parameters

from bookwyrm import forms, models
from bookwyrm.settings import DOMAIN
from bookwyrm.views.helpers import set_language

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Edit2FA(View):
    """change 2FA settings as logged in user"""

    def get(self, request):
        """Two Factor auth page"""
        data = {"form": forms.ConfirmPasswordForm()}
        return TemplateResponse(request, "preferences/2fa.html", data)

    @method_decorator(sensitive_post_parameters("password"))
    def post(self, request):
        """check the user's password"""
        form = forms.ConfirmPasswordForm(request.POST, instance=request.user)
        # TODO: display an error
        if not form.is_valid():
            data = {"form": form}
            return TemplateResponse(request, "preferences/2fa.html", data)
        qr_form = forms.Confirm2FAForm(request.POST, instance=request.user)
        data = {
            "password_confirmed": True,
            "qrcode": self.create_qr_code(request.user),
            "form": qr_form,
        }
        return TemplateResponse(request, "preferences/2fa.html", data)

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
        qr = qrcode.QRCode(image_factory=qrcode.image.svg.SvgPathImage)
        qr.add_data(provisioning_url)
        qr.make(fit=True)
        img = qr.make_image(attrib={"fill": "black"})
        return img.to_string()


class Confirm2FA(View):
    """confirm user's 2FA settings"""

    def post(self, request):
        """confirm the 2FA works before requiring it"""
        form = forms.Confirm2FAForm(request.POST, instance=request.user)
        # TODO: show an error here
        if not form.is_valid():
            data = {"form": form}
            return redirect("prefs-2fa")
        # set the user's 2FA setting on
        request.user.two_factor_auth = True
        request.user.save(broadcast=False, update_fields=["two_factor_auth"])
        data = {"form": form, "success": True}
        return TemplateResponse(request, "preferences/2fa.html", data)


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
        return TemplateResponse(request, "preferences/2fa.html", data)


class LoginWith2FA(View):
    """Check 2FA code matches before allowing login"""

    def post(self, request):
        """Check 2FA code and allow/disallow login"""
        user = models.User.objects.get(username=request.POST.get('2fa_user'))
        form = forms.Confirm2FAForm(request.POST, instance=user)
        if not form.is_valid():
            time.sleep(2)  # make life slightly harder for bots
            data = {"form": form, "2fa_user": user, "error": "Code does not match, try again"}
            return TemplateResponse(request, "two_factor_auth/two_factor_login.html", data)

        # log the user in - we are bypassing standard login
        login(request, user)
        user.update_active_date()
        return set_language(user, redirect("/"))

class Prompt2FA(View):
    """Alert user to the existence of 2FA"""

    def get(self, request):
        return TemplateResponse(request, "two_factor_auth/two_factor_prompt.html")
