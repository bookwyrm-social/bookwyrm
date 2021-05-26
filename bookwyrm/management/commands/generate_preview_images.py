""" Generate preview images """
import sys

from django.core.management.base import BaseCommand

from bookwyrm import activitystreams, models, settings, preview_images


def generate_preview_images():
    """generate preview images"""
    print("   | Hello! I will be generating preview images for your instance.")
    print("🧑‍🎨 ⎨ This might take quite long if your instance has a lot of books and users.")
    print("   | ✧ Thank you for your patience ✧")

    # Site
    sys.stdout.write("   → Site preview image: ")
    preview_images.generate_site_preview_image_task()
    sys.stdout.write(" OK 🖼\n")


    # Users
    users = models.User.objects.filter(
        local=True,
        is_active=True,
    )
    sys.stdout.write("   → User preview images ({}): ".format(len(users)))
    for user in users:
        preview_images.generate_user_preview_image_task(user.id)
        sys.stdout.write(".")
    sys.stdout.write(" OK 🖼\n")

    # Books
    books = models.Book.objects.select_subclasses().filter()
    sys.stdout.write("   → Book preview images ({}): ".format(len(books)))
    for book in books:
        preview_images.generate_edition_preview_image_task(book.id)
        sys.stdout.write(".")
    sys.stdout.write(" OK 🖼\n")

    print("🧑‍🎨 ⎨ I’m all done! ✧ Enjoy ✧")


class Command(BaseCommand):
    help = "Generate preview images"
    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run feed builder"""
        generate_preview_images()
