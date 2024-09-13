from bookwyrm.models import User
from django.urls import include, path
from django.contrib import admin
from rest_framework import routers, viewsets, generics, permissions, serializers
admin.autodiscover()


# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        permission_classes = [permissions.IsAuthenticated]
        model = User
        fields = ["url", "username", "email", "is_staff"]


# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer



# Routers provide a way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r"v1/users", UserViewSet)
# router.register(r"v1/apps", AppViewSet)
# client_name, redirect_uris, scopes, website
# router.register(r"v1/apps/verify_credentials", AppViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", include(router.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
]
