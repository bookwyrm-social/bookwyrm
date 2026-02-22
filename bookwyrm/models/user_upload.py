"""database schema for images uploaded by users"""

from django.db import models
import time, os


def user_upload_directory_path(instance, filename):
    return "uploads/user_{0}/{1}_{2}".format(instance.user.id, time.time_ns(), filename)


class UserUpload(models.Model):
    original_name = models.TextField()
    original_content_type = models.TextField()
    original_file = models.ImageField(upload_to=user_upload_directory_path)
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="user_uploads",
    )


def user_upload_version_directory_path(instance, filename):
    return "uploads/user_{0}/{1}/{2}{3}".format(
        instance.user_upload.user.id,
        instance.user_upload.id,
        instance.max_dimension,
        os.path.splitext(filename)[1],
    )


class UserUploadVersion(models.Model):
    max_dimension = models.TextField()
    file = models.ImageField(upload_to=user_upload_version_directory_path)
    user_upload = models.ForeignKey(
        "UserUpload",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="versions",
    )
