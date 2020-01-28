''' url routing for the app and api '''
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from fedireads import incoming, outgoing, views, settings


urlpatterns = [
    path('admin/', admin.site.urls),

    # federation endpoints
    path('inbox', incoming.shared_inbox),
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
