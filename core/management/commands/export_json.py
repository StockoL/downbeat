from pathlib import Path

from django.core.management.base import BaseCommand

from core.data import export_json


class Command(BaseCommand):
    help = "Write every Downbeat row to a JSON file (or stdout), for keeping or moving."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", help="File to write; stdout if left out")

    def handle(self, path, **options):
        data = export_json()
        if path:
            Path(path).write_text(data, encoding="utf-8")
            self.stdout.write(f"Exported to {path}")
        else:
            self.stdout.write(data)
