""" database schema for images uploaded by users """
from django.db import models

def user_upload_directory_path(instance, filename):
    return "uploads/user_{0}/{1}/{2}".format(instance.user.id, instance.id, filename)

class UserUpload(models.Model):
    original_name = models.TextField()
    original_content_type = models.TextField()
    original_file = models.ImageField(upload_to=user_upload_directory_path)
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="user_uploads"
    )

def user_upload_version_directory_path(instance, filename):
    return "uploads/user_{0}/{1}/{2}".format(instance.user_upload.user.id, instance.user_upload.id, instance.max_dimension)

class UserUploadVersion(models.Model):
    max_dimension = models.TextField()
    file = models.ImageField(upload_to=user_upload_version_directory_path)
    user_upload = models.ForeignKey(
        "UserUpload",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="versions"
    )
