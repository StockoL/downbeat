from django.core.management.base import BaseCommand, CommandError

from core.data import BackupFailed, backup


class Command(BaseCommand):
    help = "Copy the database to the backup folder (DOWNBEAT_BACKUP_DIR) and keep the newest copies."

    def add_arguments(self, parser):
        parser.add_argument("--dest", help="Folder to write to, instead of DOWNBEAT_BACKUP_DIR")
        parser.add_argument("--keep", type=int, help="How many backups to keep, instead of DOWNBEAT_BACKUP_KEEP")

    def handle(self, dest, keep, **options):
        try:
            path = backup(dest, keep)
        except BackupFailed as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Backed up to {path}")
