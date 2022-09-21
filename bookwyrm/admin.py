""" models that will show up in django admin for superuser """
from django.contrib import admin
from bookwyrm import models
from django.contrib.auth.admin import UserAdmin


class UserAdmin(admin.ModelAdmin):
    model = models.User
    filter_horizontal = ('followed_genres',)

admin.site.register(models.User, UserAdmin)
admin.site.register(models.FederatedServer)
admin.site.register(models.Connector)
admin.site.register(models.book.Genre)

class FollowedGenreAdmin(admin.ModelAdmin):
    model = models.notification.FollowedGenre
    filter_horizontal = ('genres',)

class NotificationAdmin(admin.ModelAdmin):
    model = models.notification.Notification
    filter_horizontal = ('related_users',)

admin.site.register(models.notification.FollowedGenre, FollowedGenreAdmin)
admin.site.register(models.notification.Notification, NotificationAdmin)




class EditionAdmin(admin.ModelAdmin):
    model = models.Edition
    filter_horizontal = ('genres',)

class WorksAdmin(admin.ModelAdmin):
    model = models.Work
    filter_horizontal = ('genres',)

admin.site.register(models.Edition, EditionAdmin)
admin.site.register(models.Work, WorksAdmin)
