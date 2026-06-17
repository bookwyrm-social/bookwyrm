from django.template.response import TemplateResponse

from bookwyrm.views.helpers import is_api_request, get_user_from_username


class PrivateProfileMixin:
    def dispatch(self, request, *args, **kwargs):
        if is_api_request(request):
            # API reveals no private activities
            return super().dispatch(request, *args, **kwargs)

        username = kwargs.get("username")
        if not username:
            # Should not reach this line unless the mixin is used in inappropriate view,
            # which I think should be counted as noop
            return super().dispatch(request, *args, **kwargs)

        target_user = get_user_from_username(request.user, username)
        is_self = target_user is request.user
        if is_self or target_user.is_visible_to(request.user.id):
            request.target_user = target_user
            return super().dispatch(request, *args, **kwargs)

        return TemplateResponse(
            request,
            "user/user.html",
            {"user": target_user, "is_self": False, "is_locked": True},
        )
