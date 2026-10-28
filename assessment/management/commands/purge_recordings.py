from django.core.management.base import BaseCommand

from assessment import recordings


class Command(BaseCommand):
    help = "Remove references to recordings that may no longer be kept (rule 15), and list the files to delete."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List what would go, and change nothing")

    def handle(self, dry_run, **options):
        found = recordings.paths(recordings.due()) if dry_run else recordings.purge()
        if not found:
            self.stdout.write("Nothing to remove.")
            return
        self.stdout.write(("Would remove" if dry_run else "Removed") + " references to these recordings. Delete the files too:")
        for path in found:
            self.stdout.write(f"  {path}")
