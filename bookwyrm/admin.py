""" models that will show up in django admin for superuser """
from django.contrib import admin
from bookwyrm import models
from django.contrib.auth.admin import UserAdmin

admin.site.register(models.User)
admin.site.register(models.FederatedServer)
admin.site.register(models.Connector)
admin.site.register(models.book.Genre)

class BookAdmin(admin.ModelAdmin):
    model = models.Book
    filter_horizontal = ('genres',)

admin.site.register(models.Book, BookAdmin)
