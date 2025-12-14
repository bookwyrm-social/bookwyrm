from django.core.management.base import BaseCommand


class MergeCommand(BaseCommand):
    """base class for merge commands"""

    def add_arguments(self, parser):
        """add the arguments for this command"""
        parser.add_argument("--canonical", type=int, required=True)
        parser.add_argument("--other", type=int, required=True)
        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="don't actually merge, only print what would happen",
        )

    def handle(self, *args, **options):
        """merge the two objects"""
        model = self.MODEL

        try:
            canonical = model.objects.get(id=options["canonical"])
        except model.DoesNotExist:
            print("canonical book doesn’t exist!")
            return
        try:
            other = model.objects.get(id=options["other"])
        except model.DoesNotExist:
            print("other book doesn’t exist!")
            return

        absorbed_fields = other.merge_into(canonical, dry_run=options["dry_run"])

        action = "would be" if options["dry_run"] else "has been"
        print(f"{other.remote_id} {action} merged into {canonical.remote_id}")
        print(f"absorbed fields: {absorbed_fields}")
