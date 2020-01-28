"""fedireads URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from fedireads import incoming, outgoing, views, settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # federation endpoints
    path('user/<str:username>.json', incoming.get_actor),
    path('user/<str:username>/inbox', incoming.inbox),
    path('user/<str:username>/outbox', outgoing.outbox),
    path('.well-known/webfinger', incoming.webfinger),

    # ui views
    path('', views.home),
    path('login/', views.user_login),
    path('logout/', views.user_logout),
    path('user/<str:username>', views.user_profile),
    path('user/<str:username>/edit/', views.user_profile_edit),
    path('book/<str:book_identifier>', views.book_page),

    # internal action endpoints
    path('review/', views.review),
    path('shelve/<str:shelf_id>/<int:book_id>', views.shelve),
    path('follow/', views.follow),
    path('unfollow/', views.unfollow),
    path('search/', views.search),
    path('upload-avatar/', views.upload_avatar),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
