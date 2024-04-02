""" Remove preview images for remote users """
from django.core.management.base import BaseCommand
from django.db.models import Q

from bookwyrm import models, preview_images


# pylint: disable=line-too-long
class Command(BaseCommand):
    """Remove preview images for remote users"""

    help = "Remove preview images for remote users"

    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """generate preview images"""
        self.stdout.write(
            "   | Hello! I will be removing preview images from remote users."
        )
        self.stdout.write(
            "🧑‍🚒 ⎨ This might take quite long if your instance has a lot of remote users."
        )
        self.stdout.write("   | ✧ Thank you for your patience ✧")

        users = models.User.objects.filter(local=False).exclude(
            Q(preview_image="") | Q(preview_image=None)
        )

        if len(users) > 0:
            self.stdout.write(
                f"   → Remote user preview images ({len(users)}): ", ending=""
            )
            for user in users:
                preview_images.remove_user_preview_image_task.delay(user.id)
                self.stdout.write(".", ending="")
            self.stdout.write(" OK 🖼")
        else:
            self.stdout.write(f"   | There was no remote users with preview images.")

        self.stdout.write("🧑‍🚒 ⎨ I’m all done! ✧ Enjoy ✧")
