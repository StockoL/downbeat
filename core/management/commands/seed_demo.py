"""
Disposable demo data for building and trying things out. Never run by migrations, so a real
install still starts from the first-run setup with nothing in it.

    set DOWNBEAT_DB=demo.sqlite3
    python manage.py migrate
    python manage.py seed_demo

Pupils are invented: first name and surname initial only, drawn from a fixed seed so every
run gives the same school.
"""

import datetime
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.data import delete_all
from notes.models import Note, NoteType, SpokenTo
from pupils.models import FlagType, PupilFlag
from rooms.models import Room, Seat, SeatAssignment, SeatingPlan
from rooms.seating import create_plan
from timetable.models import Class, Pupil, Session, SessionAttendance, Slot, Timetable
from timetable.services import generate_sessions

FIRST_NAMES = [
    "Aleya", "Jojo", "Sam", "Priya", "Ollie", "Maya", "Kofi", "Ellie", "Ravi", "Freya", "Tom", "Zara",
    "Leo", "Amara", "Finn", "Isla", "Yusuf", "Ruby", "Noah", "Hana", "Callum", "Ava", "Dev", "Niamh",
    "Ibrahim", "Lily", "Oscar", "Sofia", "Kai", "Grace", "Tariq", "Erin", "Theo", "Aisha", "Rory",
    "Mia", "Ben", "Chloe", "Arjun", "Poppy", "Jack", "Nia", "Ethan", "Layla", "Harvey", "Ada", "Max",
    "Imogen", "Musa", "Holly", "Dylan", "Sienna", "Reuben", "Esme", "Ali", "Martha", "Jude", "Tilly",
]
INITIALS = "ABCDEFGHJKLMNPRSTW"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo-downbeat"
INSTRUMENTS = ["Piano", "Violin", "Guitar", "Drums", "Flute", "Cello", "Trumpet", "Clarinet", "Voice"]

PERIODS = [
    ("P1", "08:50", "09:50"), ("P2", "09:50", "10:50"), ("P3", "11:10", "12:10"),
    ("Lunch", "12:10", "13:00"), ("P4", "13:00", "14:00"), ("P5", "14:00", "15:00"),
    ("After school", "15:10", "16:10"),
]

NOTE_TYPES = [
    # label, icon, house point, actionable
    ("House point", "★", True, False),
    ("Great answer", "✓", False, False),
    ("Off task", "↯", False, False),
    ("Chase homework", "!", False, True),
    ("Kit missing", "🎧", False, True),
]

FLAG_TYPES = [
    # private label, palette colour, category, seating rule, what works
    ("Needs a word before the lesson", 1, "attention", "near_teacher", "Quiet check-in at the door; a job early on."),
    ("Hearing: seat near the front", 5, "adjustment", "front", "Face the class when talking; written instructions."),
    ("Young carer", 7, "other", "none", "Flexibility on homework deadlines."),
]

# name, year group, home room, size
CLASSES = [
    ("7A Mu", 7, "M1", 26),
    ("8X Mu", 8, "M1", 28),
    ("9Y Mu", 9, "M2", 16),
    ("10 GCSE", 10, "M2", 12),
    ("11 GCSE", 11, "M2", 10),
]

# class, week, day (0 = Monday), period
SLOTS = [
    ("7A Mu", "A", 0, "P1"), ("7A Mu", "B", 2, "P3"),
    ("8X Mu", "A", 0, "P3"), ("8X Mu", "A", 3, "P2"), ("8X Mu", "B", 1, "P4"),
    ("9Y Mu", "A", 1, "P2"), ("9Y Mu", "B", 3, "P1"),
    ("10 GCSE", "A", 1, "P5"), ("10 GCSE", "A", 4, "P1"), ("10 GCSE", "B", 0, "P2"), ("10 GCSE", "B", 4, "P3"),
    ("11 GCSE", "A", 2, "P1"), ("11 GCSE", "B", 2, "P5"), ("11 GCSE", "B", 4, "P4"),
    ("Choir", "A", 2, "Lunch"), ("Choir", "B", 2, "Lunch"),
    ("Choir", "A", 1, "After school"), ("Choir", "B", 1, "After school"),
]


class Command(BaseCommand):
    help = "Fill an empty database with disposable demo data. Use a separate database (DOWNBEAT_DB)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete everything first. Refused on the default db.sqlite3.",
        )

    def handle(self, reset, **options):
        db_name = str(settings.DATABASES["default"]["NAME"])
        if reset:
            if db_name == str(settings.BASE_DIR / "db.sqlite3"):
                raise CommandError("--reset won't touch db.sqlite3. Set DOWNBEAT_DB to a demo database first.")
            delete_all()
        elif Timetable.objects.exists():
            raise CommandError("This database already has data. Use a fresh one, or --reset on a demo database.")

        rng = random.Random(2026)
        today = timezone.localdate()
        with transaction.atomic():
            counts = self.seed(rng, today)
            made_account = not get_user_model().objects.exists()
            if made_account:
                get_user_model().objects.create_user(DEMO_USERNAME, password=DEMO_PASSWORD)
        if made_account:
            self.stdout.write(f"Sign in as {DEMO_USERNAME} / {DEMO_PASSWORD} (demo database only).")
        self.stdout.write(self.style.SUCCESS(
            "Demo data in {db}: {pupils} pupils, {classes} classes, {rooms} rooms, {sessions} sessions, {notes} notes.".format(
                db=db_name, **counts,
            )
        ))

    def seed(self, rng, today):
        timetable = Timetable.objects.create(
            name="Demo 2026–27", week_cycle=2,
            periods=[{"label": label, "start": start, "end": end} for label, start, end in PERIODS],
        )
        note_types = [
            NoteType.objects.create(label=label, icon=icon, is_house_point=hp, is_actionable_default=act, order=i)
            for i, (label, icon, hp, act) in enumerate(NOTE_TYPES)
        ]
        rooms = {"M1": self.classroom(), "M2": self.keyboard_room(), "Hall": self.hall()}

        # Pupils, unique by name within the school so the demo reads clearly.
        names = [(f, i) for f in FIRST_NAMES for i in INITIALS]
        rng.shuffle(names)
        classes = {}
        for name, year, _, size in CLASSES:
            klass = Class.objects.create(name=name, year_group=year)
            for _ in range(size):
                first, initial = names.pop()
                plays = rng.random() < 0.3
                pupil = Pupil.objects.create(
                    first_name=first, surname_initial=initial, year_group=year,
                    instrument=rng.choice(INSTRUMENTS) if plays else "",
                    lessons_in_school=plays and rng.random() < 0.6,
                )
                klass.pupils.add(pupil)
            classes[name] = klass
        flag_types = [
            FlagType.objects.create(label=label, colour=colour, category=category, placement_rule=rule, what_works=works)
            for label, colour, category, rule, works in FLAG_TYPES
        ]
        for pupil in rng.sample(list(Pupil.objects.all()), 12):
            for flag_type in rng.sample(flag_types, rng.choice([1, 1, 1, 2])):
                PupilFlag.objects.create(pupil=pupil, flag_type=flag_type, since=today - datetime.timedelta(days=rng.randint(10, 200)))

        choir = Class.objects.create(name="Choir", kind=Class.CO_CURRICULAR)
        everyone = list(Pupil.objects.all())
        choir.pupils.add(*rng.sample(everyone, 24))
        classes["Choir"] = choir

        homes = {name: room for name, _, room, _ in CLASSES} | {"Choir": "Hall"}
        for klass_name, week, day, period in SLOTS:
            Slot.objects.create(
                timetable=timetable, week=week, day=day, period=period,
                room=rooms[homes[klass_name]], klass=classes[klass_name],
            )

        # Seat every class in its home room, filling front zones first.
        for name, klass in classes.items():
            self.seat(klass, rooms[homes[name]], today, rng)

        # Last week to the end of next week; this week is week A.
        monday = today - datetime.timedelta(days=today.weekday())
        last_monday = monday - datetime.timedelta(days=7)
        generate_sessions(timetable, last_monday, monday + datetime.timedelta(days=11), first_week="B")

        # One 8X lesson moved to the hall, where 8X has no plan: the room view offers to seat them by zone.
        moved = Session.objects.filter(klass=classes["8X Mu"], date__gte=today).order_by("date").first()
        if moved:
            moved.room, moved.status = rooms["Hall"], Session.MOVED
            moved.save()
        SeatingPlan.objects.filter(klass=classes["8X Mu"], room=rooms["Hall"]).delete()

        # History: past lessons were taught, with notes, actions and spoken-to.
        past = Session.objects.filter(date__lt=today).select_related("klass")
        for session in past:
            session.status = Session.TAUGHT
            session.save(update_fields=["status"])
            pupils = list(session.klass.pupils.all())
            start, end = timetable.period_times(session.period)
            lesson_start = timezone.make_aware(datetime.datetime.combine(session.date, start))
            lesson_end = timezone.make_aware(datetime.datetime.combine(session.date, end))

            def during_lesson(note, start=lesson_start, end=lesson_end):
                # Stamp the note inside its lesson, so the log reads like a real one.
                minutes = int((end - start).total_seconds() // 60)
                at = start + datetime.timedelta(minutes=rng.randint(3, minutes - 3))
                Note.objects.filter(pk=note.pk).update(created_at=at, updated_at=at)

            for pupil in rng.sample(pupils, min(len(pupils), rng.randint(3, 7))):
                note_type = rng.choices(note_types, weights=[5, 3, 2, 2, 1])[0]
                during_lesson(Note.objects.create(
                    session=session, pupil=pupil, note_type=note_type, actionable=note_type.is_actionable_default,
                    done_at=timezone.now() if note_type.is_actionable_default and rng.random() < 0.5 else None,
                ))
            if rng.random() < 0.3:
                during_lesson(Note.objects.create(
                    session=session, pupil=rng.choice(pupils), text="Brought own instrument in", actionable=False,
                ))
            for pupil in rng.sample(pupils, len(pupils) * 2 // 3):
                SpokenTo.objects.create(session=session, pupil=pupil)
            for pupil in rng.sample(pupils, min(2, len(pupils))):
                SessionAttendance.objects.create(session=session, pupil=pupil, present=False)

        return {
            "pupils": Pupil.objects.count(), "classes": Class.objects.count(), "rooms": Room.objects.count(),
            "sessions": Session.objects.count(), "notes": Note.objects.count(),
        }

    # --- Rooms -----------------------------------------------------------------

    def classroom(self):
        """Six rows of five, teacher at the front (bottom of the canvas). Front two rows are 'front'."""
        room = Room.objects.create(name="M1", canvas_width=900, canvas_height=600, teacher_x=450, teacher_y=560)
        for row in range(6):
            y = 40 + row * 72
            for col in range(5):
                x = 70 + col * 160
                zone = "front" if row >= 4 else "back" if row <= 1 else ""
                Seat.objects.create(
                    room=room, x=x, y=y, label=f"{chr(65 + row)}{col + 1}", zone=zone,
                    near_teacher=row == 5 and col in (1, 2, 3),
                )
        return room

    def keyboard_room(self):
        """Keyboards round three walls, a carpet in the middle, teacher at the board on the left."""
        room = Room.objects.create(name="M2", canvas_width=900, canvas_height=600, teacher_x=40, teacher_y=300)
        n = 0
        for x in range(160, 800, 100):  # top wall
            n += 1
            Seat.objects.create(room=room, x=x, y=20, label=f"K{n}", zone="keyboard")
        for y in range(120, 480, 70):  # right wall
            n += 1
            Seat.objects.create(room=room, x=800, y=y, label=f"K{n}", zone="keyboard")
        for x in range(160, 800, 100):  # bottom wall
            n += 1
            Seat.objects.create(room=room, x=x, y=536, label=f"K{n}", zone="keyboard")
        for i in range(8):  # carpet
            Seat.objects.create(
                room=room, x=300 + (i % 4) * 95, y=230 + (i // 4) * 70, label=f"C{i + 1}", zone="carpet",
                near_teacher=i % 4 == 0,
            )
        return room

    def hall(self):
        """Stage at the top; four long rows facing it."""
        room = Room.objects.create(name="Hall", canvas_width=1100, canvas_height=600, teacher_x=550, teacher_y=40)
        for row in range(4):
            for col in range(10):
                Seat.objects.create(
                    room=room, x=50 + col * 100, y=140 + row * 110, label=f"{row + 1}-{col + 1}",
                    zone="front" if row == 0 else "back" if row == 3 else "",
                )
        return room

    def seat(self, klass, room, today, rng):
        plan, _ = create_plan(klass, room, today - datetime.timedelta(days=30))
        pupils = list(klass.pupils.all())
        rng.shuffle(pupils)
        seats = list(room.seats.all())
        rng.shuffle(seats)
        for seat, pupil in zip(seats, pupils[: len(seats) - 1], strict=False):  # leave one pupil unseated, as happens
            SeatAssignment.objects.create(seating_plan=plan, seat=seat, pupil=pupil, locked=rng.random() < 0.1)
