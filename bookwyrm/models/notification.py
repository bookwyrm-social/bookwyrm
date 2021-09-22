""" alert a user to activity """
from django.db import models
from django.dispatch import receiver
from .base_model import BookWyrmModel
from . import Boost, Favorite, ImportJob, Report, Status, User


NotificationType = models.TextChoices(
    "NotificationType",
    "FAVORITE REPLY MENTION TAG FOLLOW FOLLOW_REQUEST BOOST IMPORT ADD REPORT",
)


class Notification(BookWyrmModel):
    """you've been tagged, liked, followed, etc"""

    user = models.ForeignKey("User", on_delete=models.CASCADE)
    related_book = models.ForeignKey("Edition", on_delete=models.CASCADE, null=True)
    related_user = models.ForeignKey(
        "User", on_delete=models.CASCADE, null=True, related_name="related_user"
    )
    related_status = models.ForeignKey("Status", on_delete=models.CASCADE, null=True)
    related_import = models.ForeignKey("ImportJob", on_delete=models.CASCADE, null=True)
    related_list_item = models.ForeignKey(
        "ListItem", on_delete=models.CASCADE, null=True
    )
    related_report = models.ForeignKey("Report", on_delete=models.CASCADE, null=True)
    read = models.BooleanField(default=False)
    notification_type = models.CharField(
        max_length=255, choices=NotificationType.choices
    )

    def save(self, *args, **kwargs):
        """save, but don't make dupes"""
        # there's probably a better way to do this
        if self.__class__.objects.filter(
            user=self.user,
            related_book=self.related_book,
            related_user=self.related_user,
            related_status=self.related_status,
            related_import=self.related_import,
            related_list_item=self.related_list_item,
            related_report=self.related_report,
            notification_type=self.notification_type,
        ).exists():
            return
        super().save(*args, **kwargs)

    class Meta:
        """checks if notifcation is in enum list for valid types"""

        constraints = [
            models.CheckConstraint(
                check=models.Q(notification_type__in=NotificationType.values),
                name="notification_type_valid",
            )
        ]


@receiver(models.signals.post_save, sender=Favorite)
# pylint: disable=unused-argument
def notify_on_fav(sender, instance, *args, **kwargs):
    """someone liked your content, you ARE loved"""
    if not instance.status.user.local or instance.status.user == instance.user:
        return
    Notification.objects.create(
        user=instance.status.user,
        notification_type="FAVORITE",
        related_user=instance.user,
        related_status=instance.status,
    )


@receiver(models.signals.post_delete, sender=Favorite)
# pylint: disable=unused-argument
def notify_on_unfav(sender, instance, *args, **kwargs):
    """oops, didn't like that after all"""
    if not instance.status.user.local:
        return
    Notification.objects.filter(
        user=instance.status.user,
        related_user=instance.user,
        related_status=instance.status,
        notification_type="FAVORITE",
    ).delete()


@receiver(models.signals.post_save)
# pylint: disable=unused-argument
def notify_user_on_mention(sender, instance, *args, **kwargs):
    """creating and deleting statuses with @ mentions and replies"""
    if not issubclass(sender, Status):
        return

    if instance.deleted:
        Notification.objects.filter(related_status=instance).delete()
        return

    if (
        instance.reply_parent
        and instance.reply_parent.user != instance.user
        and instance.reply_parent.user.local
    ):
        Notification.objects.create(
            user=instance.reply_parent.user,
            notification_type="REPLY",
            related_user=instance.user,
            related_status=instance,
        )
    for mention_user in instance.mention_users.all():
        # avoid double-notifying about this status
        if not mention_user.local or (
            instance.reply_parent and mention_user == instance.reply_parent.user
        ):
            continue
        Notification.objects.create(
            user=mention_user,
            notification_type="MENTION",
            related_user=instance.user,
            related_status=instance,
        )


@receiver(models.signals.post_save, sender=Boost)
# pylint: disable=unused-argument
def notify_user_on_boost(sender, instance, *args, **kwargs):
    """boosting a status"""
    if (
        not instance.boosted_status.user.local
        or instance.boosted_status.user == instance.user
    ):
        return

    Notification.objects.create(
        user=instance.boosted_status.user,
        related_status=instance.boosted_status,
        related_user=instance.user,
        notification_type="BOOST",
    )


@receiver(models.signals.post_delete, sender=Boost)
# pylint: disable=unused-argument
def notify_user_on_unboost(sender, instance, *args, **kwargs):
    """unboosting a status"""
    Notification.objects.filter(
        user=instance.boosted_status.user,
        related_status=instance.boosted_status,
        related_user=instance.user,
        notification_type="BOOST",
    ).delete()


@receiver(models.signals.post_save, sender=ImportJob)
# pylint: disable=unused-argument
def notify_user_on_import_complete(sender, instance, *args, **kwargs):
    """we imported your books! aren't you proud of us"""
    if not instance.complete:
        return
    Notification.objects.create(
        user=instance.user,
        notification_type="IMPORT",
        related_import=instance,
    )


@receiver(models.signals.post_save, sender=Report)
# pylint: disable=unused-argument
def notify_admins_on_report(sender, instance, *args, **kwargs):
    """something is up, make sure the admins know"""
    # moderators and superusers should be notified
    admins = User.objects.filter(
        models.Q(user_permissions__name__in=["moderate_user", "moderate_post"])
        | models.Q(is_superuser=True)
    ).all()
    for admin in admins:
        Notification.objects.create(
            user=admin,
            related_report=instance,
            notification_type="REPORT",
        )
