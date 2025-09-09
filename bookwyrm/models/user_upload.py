""" database schema for images uploaded by users """
from django.db import models

def user_directory_path(instance, filename):
    return "uploads/user_{0}/{1}".format(instance.user.id, filename)

class UserUpload(models.Model):
    original_name = models.TextField()
    original_content_type = models.TextField()
    file = models.ImageField(upload_to=user_directory_path)
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
