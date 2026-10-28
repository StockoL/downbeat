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

from assessment.models import Band, Check, Component, Exemplar, Feedback, FeedbackCode, Observation, Strand
from core.data import delete_all
from notes.models import ChecklistItem, Goal, Note, NoteType, SpokenTo
from plans.models import LessonPlan, PlanActivity, Resource, Scheme, Unit
from plans.services import fill_from_unit
from pupils.models import FlagType, Group, GroupMember, Loan, LoanItem, PupilFlag, Relationship
from rooms.adjacency import adjacent
from rooms.models import Room, Seat, SeatAssignment, SeatingPlan
from rooms.seating import create_plan, move
from timetable.models import Class, Pupil, PupilRotation, Rotation, Session, SessionAttendance, Slot, Timetable
from timetable.rotations import rotating
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
        house_point = next(t for t in note_types if t.is_house_point)
        Goal.objects.create(
            text="A house point in 20 lessons this week", target_count=20, counts_note_type=house_point,
            week_start=today - datetime.timedelta(days=60),
        )
        for order, text in enumerate(["Starter", "Homework set", "Exit task"]):
            ChecklistItem.objects.create(text=text, order=order)

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

        # 8X has three keep-apart pairs and two who work well together: what the shuffle is for.
        eight_x = list(classes["8X Mu"].pupils.all())
        rng.shuffle(eight_x)
        for i, kind in enumerate(["keep_apart"] * 3 + ["pair_well"] * 2):
            Relationship.objects.create(
                pupil_a=eight_x[2 * i], pupil_b=eight_x[2 * i + 1], kind=kind, source="Head of year",
            )

        # …and the first keep-apart pair has ended up side by side, for the shuffle to sort out.
        plan = SeatingPlan.objects.get(klass=classes["8X Mu"], room=rooms["M1"])
        plan.assignments.update(locked=False)
        first, second = eight_x[0], eight_x[1]
        anchor = plan.assignments.get(pupil=first).seat
        beside = next(seat for seat in rooms["M1"].seats.all() if adjacent(anchor, seat))
        move(plan, second, beside)

        # 9Y are in bands for the riffs unit, each with parts.
        nine_y = list(classes["9Y Mu"].pupils.all())
        rng.shuffle(nine_y)
        for index, (name, roles) in enumerate([
            ("Band 1", ["drums", "bass", "keys", "vocals"]),
            ("Band 2", ["drums", "keys", "guitar"]),
            ("Band 3", ["bass", "keys", "vocals", "guitar"]),
        ]):
            group = Group.objects.create(
                klass=classes["9Y Mu"], name=name, working_on="Twelve-bar riff", started=today - datetime.timedelta(days=14),
                tint=index + 1,
            )
            for role in roles:
                GroupMember.objects.create(group=group, pupil=nine_y.pop(), role=role)

        # Violin lessons rotate through the day's five periods, so some lessons have pupils out.
        weeks, slots = rotating(min(today.weekday(), 4), ["P1", "P2", "P3", "P4", "P5"], today - datetime.timedelta(days=14), 14)
        violin = Rotation.objects.create(name="Ms R, violin", slot_count=5, weeks=weeks, slots=slots)
        learners = [p for p in Pupil.objects.filter(lessons_in_school=True)][:5]
        for index, pupil in enumerate(learners):
            PupilRotation.objects.create(pupil=pupil, rotation=violin, slot_index=index)

        # The department's loan cupboard: two things out, one of them overdue.
        items = [LoanItem.objects.create(name="Headphones", kind="headphones", identifier=str(n)) for n in range(1, 7)]
        items += [LoanItem.objects.create(name="Ukulele", kind="ukulele", identifier=str(n)) for n in range(1, 3)]
        borrowers = rng.sample(list(Pupil.objects.all()), 2)
        Loan.objects.create(item=items[0], pupil=borrowers[0], out_at=timezone.now() - datetime.timedelta(days=9),
                            due=today - datetime.timedelta(days=2))
        Loan.objects.create(item=items[6], pupil=borrowers[1], out_at=timezone.now() - datetime.timedelta(days=1),
                            due=today + datetime.timedelta(days=6))

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

        # A skeleton curriculum: Year 8 blues and Year 9 riffs, six lessons each, filled into the timetable.
        units = {}
        for year, unit_name, ideas in [
            (8, "Blues", ["Twelve-bar pattern", "Walking bass", "Blues scale improvising", "Lyrics in AAB form", "Putting it together", "Performance"]),
            (9, "Riffs", ["What makes a riff", "Riffs on keyboards", "Layering riffs", "Band arrangement", "Rehearsal", "Performance"]),
        ]:
            scheme = Scheme.objects.create(name=f"Year {year}", year_group=year)
            unit = Unit.objects.create(scheme=scheme, name=unit_name, order=1, lessons_planned=6,
                                       purpose="Hear who can keep a groove going and adapt it.")
            for order, objective in enumerate(ideas, start=1):
                lesson = LessonPlan.objects.create(unit=unit, order=order, objective=objective, homework="Listen to one track from the playlist.")
                for position, (text, minutes) in enumerate([("Starter: call and response", 5), (f"{objective}: demo", 10),
                                                            (f"{objective}: in pairs", 25), ("Share and feedback", 10)]):
                    PlanActivity.objects.create(lesson_plan=lesson, order=position, text=text, minutes=minutes)
                if order in (1, 4):
                    Resource.objects.create(lesson_plan=lesson, title=f"{unit_name} sheet {order}", needs_print=True, copies=30,
                                            path_or_url=f"Music/Y{year}/{unit_name}/sheet-{order}.pdf")
            units[year] = unit

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

        # Assessment frame: the department's strands and bands, and each unit's components.
        strands = {name: Strand.objects.create(name=name, order=i) for i, name in enumerate(["Performing", "Composing", "Listening"])}
        for i, name in enumerate(["Developing", "Secure", "Expert"]):
            Band.objects.create(name=name, order=i)
        for year, rows in [
            (8, [("Keeps a steady pulse in the twelve-bar", "Performing", "Play along with the click track"),
                 ("Plays a walking bass that fits the chords", "Performing", "Add the fifth on beat three"),
                 ("Improvises using the blues scale", "Composing", "Start and end phrases on the root"),
                 ("Hears and names the chord changes", "Listening", "Count the bars before each change")]),
            (9, [("Plays a riff in time with the band", "Performing", "Lock in with the drummer's snare"),
                 ("Layers a second riff that fits", "Composing", "Leave space for the first riff"),
                 ("Spots how a riff is varied", "Listening", "Listen for what stays the same")]),
        ]:
            made = []
            for order, (text, strand, step) in enumerate(rows):
                made.append(Component.objects.create(unit=units[year], order=order, text=text, strand=strands[strand],
                                                     next_step_default=step, cumulative_of=made[0] if order == 1 else None))
            FeedbackCode.objects.create(unit=units[year], number=1, text="Count in before you start", component=made[0])
            FeedbackCode.objects.create(unit=units[year], number=2, text="Leave space between phrases", component=made[-1])

        # Hinge checks for the first four lessons of each unit, each wrong answer tagged with its misconception.
        hinges = {
            8: [("How many bars are in a twelve-bar blues?", "Twelve, in three lines of four",
                 [("Twelve beats", "Confuses bars with beats"), ("Eight", "Expects a pop verse length")]),
                ("Which notes does a walking bass mostly use?", "Chord notes, stepping between them",
                 [("Only the root", "Hasn't heard the line move"), ("Any scale notes, at random", "Thinks walking means free")]),
                ("Which note of the blues scale is the blue note?", "The flattened fifth",
                 [("The root", "Mixes up home and colour"), ("The major third", "Confuses the blues scale with the major")]),
                ("In AAB form, which line is different?", "The third",
                 [("The first", "Reads the letters as a ranking"), ("None of them", "Thinks A means any line")])],
            9: [("What makes a riff a riff?", "A short pattern that repeats",
                 [("A long tune that never repeats", "Mixes up riff and melody"), ("Any guitar part", "Ties riffs to one instrument")]),
                ("A riff is four beats long. How many times does it fit in two bars of 4/4?", "Twice",
                 [("Four times", "Counts beats, not bars"), ("Once", "Thinks a riff fills a bar")]),
                ("Two riffs are layered. What must they share?", "The same pulse and key",
                 [("The same rhythm", "Thinks layering means doubling"), ("The same instrument", "Confuses texture with timbre")]),
                ("Who keeps the groove steady in a band?", "The drums and bass together",
                 [("The singer", "Follows the loudest part"), ("Whoever plays loudest", "Equates volume with time")])],
        }
        for year, rows in hinges.items():
            for order, (question, answer, wrong) in enumerate(rows, start=1):
                Check.objects.create(
                    lesson_plan=units[year].lessons.get(order=order), question=question, answer=answer, threshold=80,
                    distractors=[{"text": text, "misconception": why} for text, why in wrong],
                )
        units[8].check_responses = True  # one unit opts in to pupils' answers, to show the sweep's grid
        units[8].save(update_fields=["check_responses"])

        last_monday = today - datetime.timedelta(days=today.weekday() + 7)
        fill_from_unit(classes["8X Mu"], units[8], from_date=last_monday)
        fill_from_unit(classes["9Y Mu"], units[9], from_date=last_monday)

        # Most past lessons with a check had a decision, made partway through.
        for session in Session.objects.filter(date__lt=today, lesson__checks__isnull=False):
            if rng.random() < 0.75:
                start, _ = timetable.period_times(session.period)
                minutes = rng.randint(15, 35)
                asked = session.lesson.checks.get().ask_in(session, decision=rng.choice(Check.DECISIONS)[0], minutes_in=minutes)
                when = timezone.make_aware(datetime.datetime.combine(session.date, start)) + datetime.timedelta(minutes=minutes)
                Check.objects.filter(pk=asked.pk).update(created_at=when, updated_at=when)

        # Observations from past lessons: a handful each, states that wander (they may go backwards),
        # each with its component's next step; and one lesson's self-assessment, entered afterwards.
        for session in Session.objects.filter(date__lt=today, lesson__unit__components__isnull=False).distinct():
            start, _ = timetable.period_times(session.period)
            components = list(session.lesson.unit.components.all())
            for pupil in rng.sample(list(session.klass.pupils.all()), 10):
                component = rng.choice(components)
                observation = Observation.objects.create(
                    session=session, pupil=pupil, component=component, next_step=component.next_step_default,
                    state=rng.choices([Observation.NOT_YET, Observation.PARTLY, Observation.SECURE], weights=[2, 4, 3])[0],
                )
                when = timezone.make_aware(datetime.datetime.combine(session.date, start)) + datetime.timedelta(minutes=rng.randint(10, 50))
                Observation.objects.filter(pk=observation.pk).update(created_at=when, updated_at=when)
        latest = Session.objects.filter(date__lt=today, klass=classes["9Y Mu"], lesson__isnull=False).order_by("-date").first()
        if latest:
            first = latest.lesson.unit.components.first()
            for pupil in latest.klass.pupils.all():
                Observation.objects.create(session=latest, pupil=pupil, component=first, assessor="self",
                                           state=rng.choice([Observation.PARTLY, Observation.SECURE]), next_step=first.next_step_default)

        # Feedback: three parts, one anchored in a recording for a pupil whose family agreed to recordings.
        recorded = classes["9Y Mu"].pupils.first()
        recorded.recording_permitted = recorded.exemplar_reuse_permitted = True
        recorded.save(update_fields=["recording_permitted", "exemplar_reuse_permitted"])
        if latest:
            first = latest.lesson.unit.components.first()
            Feedback.objects.create(
                session=latest, pupil=recorded, component=first, done_well="The riff sits right on the beat.",
                develop="It speeds up when the band comes in.", how="Watch the drummer's hi-hat and lock to it.",
                recording_path=f"Music/Recordings/9Y/{recorded.first_name}-riff-week-2.m4a", recording_seconds=102,
            )
            others = list(latest.klass.pupils.exclude(pk=recorded.pk))
            for pupil, (develop, how) in zip(rng.sample(others, 2), [
                ("The second riff clashes on beat three.", "Try starting it on the off-beat."),
                ("The ending is untidy.", "Agree a signal for the last bar."),
            ], strict=True):
                Feedback.objects.create(session=latest, pupil=pupil, done_well="Kept going all the way through.", develop=develop, how=how)

        # Recordings: the recorded pupil's riff, week by week, for their timeline; the department's
        # exemplars, one of them the recorded pupil's (their family agreed to reuse); and a pupil whose
        # delete-by date has passed, so Settings → Data has a recording to remove.
        nine_y_past = list(Session.objects.filter(klass=classes["9Y Mu"], date__lt=today, lesson__isnull=False).order_by("date"))
        riff = units[9].components.first()
        for session, state, week in zip(nine_y_past, [Observation.PARTLY, Observation.SECURE], [1, 2], strict=False):
            heard = Observation.objects.create(session=session, pupil=recorded, component=riff, state=state, next_step=riff.next_step_default,
                                               recording_path=f"Music/Recordings/9Y/{recorded.first_name}-riff-week-{week}.m4a")
            start, _ = timetable.period_times(session.period)
            when = timezone.make_aware(datetime.datetime.combine(session.date, start)) + datetime.timedelta(minutes=20)
            Observation.objects.filter(pk=heard.pk).update(created_at=when, updated_at=when)
        for year in (8, 9):
            first = units[year].components.first()
            for level in ("low", "mid", "high"):
                Exemplar.objects.create(unit=units[year], component=first, level=level, note=f"Department exemplar, {level}",
                                        recording_path=f"Music/Exemplars/Y{year}/{units[year].name.lower()}-{level}.m4a")
        Exemplar.objects.create(unit=units[9], component=riff, level="high", source_pupil=recorded, note="Locks to the hi-hat throughout",
                                recording_path=f"Music/Recordings/9Y/{recorded.first_name}-riff-week-2.m4a")
        leaver = classes["9Y Mu"].pupils.exclude(pk=recorded.pk).first()
        leaver.recording_permitted = True
        leaver.recordings_delete_by = today - datetime.timedelta(days=3)
        leaver.save(update_fields=["recording_permitted", "recordings_delete_by"])
        if nine_y_past:
            Observation.objects.create(session=nine_y_past[0], pupil=leaver, component=riff, state=Observation.PARTLY,
                                       next_step=riff.next_step_default, recording_path=f"Music/Recordings/9Y/{leaver.first_name}-riff-week-1.m4a")

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
