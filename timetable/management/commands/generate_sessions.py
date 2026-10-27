import datetime

from django.core.management.base import BaseCommand, CommandError

from timetable.models import Timetable
from timetable.services import generate_sessions


class Command(BaseCommand):
    help = "Create sessions from the active timetable's slots for a date range."

    def add_arguments(self, parser):
        parser.add_argument("start", type=datetime.date.fromisoformat, help="First date, YYYY-MM-DD")
        parser.add_argument("end", type=datetime.date.fromisoformat, help="Last date, YYYY-MM-DD")
        parser.add_argument(
            "--first-week", choices=["A", "B"], default="A",
            help="Which week the start date falls in, for a two-week timetable",
        )

    def handle(self, start, end, first_week, **options):
        if end < start:
            raise CommandError("The end date is before the start date.")
        timetable = Timetable.active()
        if timetable is None:
            raise CommandError("There is no timetable yet. Run the first-run setup.")
        created = generate_sessions(timetable, start, end, first_week)
        self.stdout.write(f"Created {created} session{'s' if created != 1 else ''}.")
