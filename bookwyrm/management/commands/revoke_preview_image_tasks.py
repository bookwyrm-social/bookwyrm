""" Actually let's not generate those preview images  """
import json
from django.core.management.base import BaseCommand
from bookwyrm.tasks import app


class Command(BaseCommand):
    """Find and revoke image tasks"""

    # pylint: disable=unused-argument
    def handle(self, *args, **options):
        """revoke nonessential low priority tasks"""
        types = [
            "bookwyrm.preview_images.generate_edition_preview_image_task",
            "bookwyrm.preview_images.generate_user_preview_image_task",
        ]
        self.stdout.write("   | Finding tasks of types:")
        self.stdout.write("\n".join(types))
        with app.pool.acquire(block=True) as conn:
            tasks = conn.default_channel.client.lrange("low_priority", 0, -1)
            self.stdout.write(f"   | Found {len(tasks)} task(s) in low priority queue")

        revoke_ids = []
        for task in tasks:
            task_json = json.loads(task)
            task_type = task_json.get("headers", {}).get("task")
            if task_type in types:
                revoke_ids.append(task_json.get("headers", {}).get("id"))
                self.stdout.write(".", ending="")
        self.stdout.write(f"\n   | Revoking {len(revoke_ids)} task(s)")
        app.control.revoke(revoke_ids)
