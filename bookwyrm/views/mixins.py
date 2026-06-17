from django.template.response import TemplateResponse

from bookwyrm.views.helpers import is_api_request, get_user_from_username


class PrivateProfileMixin:
    def dispatch(self, request, *args, **kwargs):
        if is_api_request(request):
            # API reveals no private activities
            return super().dispatch(request, *args, **kwargs)

        username = kwargs.get("username")
        if not username:
            return super().dispatch(request, *args, **kwargs)

        target_user = get_user_from_username(request.user, username)
        is_self = target_user is request.user
        if not is_self and not target_user.is_visible_to(request.user.id):
            return TemplateResponse(
                request,
                "user/user.html",
                {"user": target_user, "is_self": False, "is_locked": True},
            )

        request.target_user = target_user
        return super().dispatch(request, *args, **kwargs)
