"""
What "next to" means in a free-placed room, and whether a seat meets a flag's seating rule.
The seating editor's lines and the shuffle both use these, so they never disagree.
"""

import math

from .models import SEAT_HEIGHT, SEAT_WIDTH

# Neighbours are judged in an ellipse, because rooms are laid out wider than they are deep:
# a seat either side, even with a seat-width gap between desks (centres 160 apart), and the
# seat directly in front or behind (a row's depth away), but not a diagonal across a gap and
# not two rows away.
REACH_ACROSS = 2.1 * SEAT_WIDTH
REACH_FRONT_TO_BACK = 1.8 * SEAT_HEIGHT
# "Near the teacher" without a painted seat: within this distance of the teacher marker.
NEAR_TEACHER_RADIUS = 220


def centre(seat):
    return seat.x + SEAT_WIDTH / 2, seat.y + SEAT_HEIGHT / 2


def distance(seat_a, seat_b):
    (ax, ay), (bx, by) = centre(seat_a), centre(seat_b)
    return math.hypot(ax - bx, ay - by)


def adjacent(seat_a, seat_b):
    (ax, ay), (bx, by) = centre(seat_a), centre(seat_b)
    reach = ((ax - bx) / REACH_ACROSS) ** 2 + ((ay - by) / REACH_FRONT_TO_BACK) ** 2
    return seat_a.id != seat_b.id and reach <= 1


def neighbours(seats):
    """{seat_id: {neighbouring seat ids}} for every seat in a room."""
    result = {seat.id: set() for seat in seats}
    for i, a in enumerate(seats):
        for b in seats[i + 1:]:
            if adjacent(a, b):
                result[a.id].add(b.id)
                result[b.id].add(a.id)
    return result


def meets_rule(rule, seat, room):
    """
    Whether a seat satisfies a flag's seating rule. Rooms don't record doors or windows yet,
    so those rules can't be checked and count as met.
    """
    if rule == "front":
        return seat.zone == "front"
    if rule == "near_teacher":
        if seat.near_teacher:
            return True
        if room.teacher_x is None:
            return False
        sx, sy = centre(seat)
        return math.hypot(sx - room.teacher_x, sy - room.teacher_y) <= NEAR_TEACHER_RADIUS
    return True
