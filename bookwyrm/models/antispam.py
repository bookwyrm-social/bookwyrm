""" Lets try NOT to sell viagra """
from django.db import models

from .user import User


class EmailBlocklist(models.Model):
    """blocked email addresses"""

    created_date = models.DateTimeField(auto_now_add=True)
    domain = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """default sorting"""

        ordering = ("-created_date",)

    @property
    def users(self):
        """find the users associated with this address"""
        return User.objects.filter(email__endswith=f"@{self.domain}")


class IPBlocklist(models.Model):
    """blocked ip addresses"""

    created_date = models.DateTimeField(auto_now_add=True)
    address = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        """default sorting"""

        ordering = ("-created_date",)


class AutoMod(models.Model):
    """rules to automatically flag suspicious activity"""
    string_match = models.CharField(max_length=200, unique=True)
    flag_users = models.BooleanField(default=True)
    flag_statuses = models.BooleanField(default=True)
    created_by = models.ForeignKey("User", on_delete=models.PROTECT)
