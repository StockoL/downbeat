"""
The shuffle: a seating arrangement that keeps every keep-apart pair apart, never moves a locked
seat, and otherwise does its best for flag seating rules and pupils who work well together.

Pure: it takes plain values and returns {seat_id: pupil_id}, so it can be tested on its own.

Hard rules (never broken; if they can't both hold, NoArrangement is raised):
  - a locked seat keeps its pupil;
  - no keep-apart pair sits in neighbouring seats.
Soft goals (scored; the best of many attempts wins):
  - each pupil's seating rules are met (worth most);
  - pair-well partners sit next to each other.
"""

import random
from dataclasses import dataclass, field

RULE_WEIGHT = 10
PAIR_WEIGHT = 3
ATTEMPTS = 40
STEP_LIMIT = 4000  # per attempt, so a hopeless case gives up quickly


class NoArrangement(Exception):
    """Every keep-apart pair can't be kept apart with these seats and locks."""


@dataclass
class Problem:
    seats: list  # seat ids
    pupils: list  # pupil ids to seat (locked pupils included; they stay put)
    neighbours: dict  # seat id -> set of neighbouring seat ids
    locked: dict = field(default_factory=dict)  # seat id -> pupil id
    keep_apart: set = field(default_factory=set)  # frozenset({pupil, pupil})
    pair_well: set = field(default_factory=set)  # frozenset({pupil, pupil})
    rules_met: dict = field(default_factory=dict)  # pupil id -> set of seat ids that meet all their rules


def score(problem, arrangement):
    seat_of = {pupil: seat for seat, pupil in arrangement.items()}
    total = 0
    for pupil, good_seats in problem.rules_met.items():
        if pupil in seat_of and seat_of[pupil] in good_seats:
            total += RULE_WEIGHT
    for pair in problem.pair_well:
        a, b = tuple(pair)
        if a in seat_of and b in seat_of and seat_of[b] in problem.neighbours[seat_of[a]]:
            total += PAIR_WEIGHT
    return total


def violations(problem, arrangement):
    """Keep-apart pairs seated next to each other. A returned arrangement always has none."""
    seat_of = {pupil: seat for seat, pupil in arrangement.items()}
    found = []
    for pair in problem.keep_apart:
        a, b = tuple(pair)
        if a in seat_of and b in seat_of and seat_of[b] in problem.neighbours[seat_of[a]]:
            found.append(pair)
    return found


def shuffle(problem, rng=None):
    rng = rng or random.Random()
    _check_locks(problem)
    best, best_score = None, -1
    for _ in range(ATTEMPTS):
        arrangement = _attempt(problem, rng)
        if arrangement is None:
            continue
        points = score(problem, arrangement)
        if points > best_score:
            best, best_score = arrangement, points
    if best is None:
        raise NoArrangement
    return best


def _check_locks(problem):
    locked = {pupil: seat for seat, pupil in problem.locked.items()}
    for pair in problem.keep_apart:
        a, b = tuple(pair)
        if a in locked and b in locked and locked[b] in problem.neighbours[locked[a]]:
            raise NoArrangement


def _attempt(problem, rng):
    """One randomised depth-first search. None if it runs out of steps."""
    partners = {}
    for pair in problem.keep_apart:
        a, b = tuple(pair)
        partners.setdefault(a, set()).add(b)
        partners.setdefault(b, set()).add(a)
    friends = {}
    for pair in problem.pair_well:
        a, b = tuple(pair)
        friends.setdefault(a, set()).add(b)
        friends.setdefault(b, set()).add(a)

    arrangement = dict(problem.locked)
    seat_of = {pupil: seat for seat, pupil in arrangement.items()}
    free = [s for s in problem.seats if s not in arrangement]
    to_place = [p for p in problem.pupils if p not in seat_of]
    rng.shuffle(to_place)
    # Hardest first: pupils with seating rules, then those with the most keep-apart partners.
    to_place.sort(key=lambda p: (p not in problem.rules_met, -len(partners.get(p, ()))))
    to_place = to_place[: len(free)]  # more pupils than seats: the rest stay unseated

    steps = [0]

    def allowed(pupil, seat):
        return all(
            seat_of.get(other) not in problem.neighbours[seat] for other in partners.get(pupil, ())
        )

    def preference(pupil, seat):
        points = rng.random()
        if seat in problem.rules_met.get(pupil, ()):
            points += RULE_WEIGHT
        if any(seat_of.get(f) in problem.neighbours[seat] for f in friends.get(pupil, ())):
            points += PAIR_WEIGHT
        return points

    def place(index):
        if index == len(to_place):
            return True
        steps[0] += 1
        if steps[0] > STEP_LIMIT:
            return False
        pupil = to_place[index]
        options = [s for s in free if s not in arrangement and allowed(pupil, s)]
        options.sort(key=lambda s: preference(pupil, s), reverse=True)
        for seat in options:
            arrangement[seat] = pupil
            seat_of[pupil] = seat
            if place(index + 1):
                return True
            del arrangement[seat]
            del seat_of[pupil]
        return False

    return dict(arrangement) if place(0) else None
