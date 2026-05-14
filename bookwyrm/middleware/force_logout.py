"""Check if user needs to reset their password and log them out"""

from django.contrib.auth import logout


class ForceLogoutMiddleware:
    """Log out any users who are flagged as needing a password reset"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.force_password_reset:
            logout(request)
        return self.get_response(request)
