"""Property tests for the shuffle: whatever the room, class and constraints, the hard rules hold."""

import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rooms.solver import NoArrangement, Problem, score, shuffle, violations


def grid_neighbours(columns, rows):
    """Seats numbered row by row; neighbours are left, right, in front and behind."""
    neighbours = {}
    for r in range(rows):
        for c in range(columns):
            seat = r * columns + c
            near = set()
            for dc, dr in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                if 0 <= c + dc < columns and 0 <= r + dr < rows:
                    near.add((r + dr) * columns + c + dc)
            neighbours[seat] = near
    return neighbours


@st.composite
def problems(draw):
    columns, rows = draw(st.integers(2, 6)), draw(st.integers(2, 5))
    neighbours = grid_neighbours(columns, rows)
    seats = list(neighbours)
    pupils = [f"p{i}" for i in range(draw(st.integers(1, len(seats) + 3)))]
    pairs = st.tuples(st.sampled_from(pupils), st.sampled_from(pupils)).filter(lambda t: t[0] != t[1]).map(frozenset)
    keep_apart = draw(st.sets(pairs, max_size=max(1, len(pupils) // 3)))
    pair_well = draw(st.sets(pairs, max_size=3)) - keep_apart
    # Lock a few pupils into seats, never two keep-apart partners side by side.
    locked = {}
    for pupil in draw(st.lists(st.sampled_from(pupils), max_size=3, unique=True)):
        seat = draw(st.sampled_from(seats))
        if seat in locked:
            continue
        clash = any(
            frozenset({pupil, other}) in keep_apart and seat in neighbours[other_seat]
            for other_seat, other in locked.items()
        )
        if not clash:
            locked[seat] = pupil
    rules_met = {
        pupil: set(draw(st.lists(st.sampled_from(seats), max_size=4)))
        for pupil in draw(st.lists(st.sampled_from(pupils), max_size=3, unique=True))
    }
    return Problem(seats=seats, pupils=pupils, neighbours=neighbours, locked=locked,
                   keep_apart=keep_apart, pair_well=pair_well, rules_met=rules_met)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(problem=problems(), seed=st.integers(0, 2**32 - 1))
def test_hard_rules_always_hold(problem, seed):
    try:
        arrangement = shuffle(problem, random.Random(seed))
    except NoArrangement:
        return  # refusing is allowed; returning a bad plan is not

    # Locked seats never move.
    for seat, pupil in problem.locked.items():
        assert arrangement[seat] == pupil
    # Keep-apart pairs are never neighbours.
    assert violations(problem, arrangement) == []
    # Nobody sits twice, and only real seats and pupils appear.
    assert len(set(arrangement.values())) == len(arrangement)
    assert set(arrangement) <= set(problem.seats)
    assert set(arrangement.values()) <= set(problem.pupils)
    # Everyone fits who can.
    assert len(arrangement) == min(len(problem.pupils), len(problem.seats))


def test_a_class_with_three_keep_apart_pairs_is_seated_apart():
    """Phase 3's "done when": a class of 28 with three keep-aparts gets a plan."""
    neighbours = grid_neighbours(6, 5)
    pupils = [f"p{i}" for i in range(28)]
    keep_apart = {frozenset({"p0", "p1"}), frozenset({"p2", "p3"}), frozenset({"p0", "p4"})}
    problem = Problem(seats=list(neighbours), pupils=pupils, neighbours=neighbours, keep_apart=keep_apart)
    arrangement = shuffle(problem, random.Random(1))
    assert violations(problem, arrangement) == [] and len(arrangement) == 28


def test_seating_rules_and_pairs_are_honoured_when_possible():
    neighbours = grid_neighbours(4, 3)
    front_row = {8, 9, 10, 11}
    problem = Problem(
        seats=list(neighbours), pupils=[f"p{i}" for i in range(10)], neighbours=neighbours,
        pair_well={frozenset({"p5", "p6"})}, rules_met={"p1": front_row, "p2": front_row},
    )
    arrangement = shuffle(problem, random.Random(7))
    assert score(problem, arrangement) == 2 * 10 + 3


def test_impossible_constraints_are_refused_not_broken():
    # Two seats side by side and a keep-apart pair to fill them.
    problem = Problem(seats=[0, 1], pupils=["a", "b"], neighbours={0: {1}, 1: {0}}, keep_apart={frozenset({"a", "b"})})
    with pytest.raises(NoArrangement):
        shuffle(problem, random.Random(0))


def test_locked_keep_apart_neighbours_are_refused():
    problem = Problem(seats=[0, 1, 2], pupils=["a", "b"], neighbours={0: {1}, 1: {0, 2}, 2: {1}},
                      locked={0: "a", 1: "b"}, keep_apart={frozenset({"a", "b"})})
    with pytest.raises(NoArrangement):
        shuffle(problem, random.Random(0))


@settings(max_examples=60, deadline=None)
@given(columns=st.integers(1, 6), rows=st.integers(1, 5), class_size=st.integers(0, 35), seed=st.integers(0, 2**32 - 1))
def test_without_hard_constraints_it_never_refuses(columns, rows, class_size, seed):
    neighbours = grid_neighbours(columns, rows)
    problem = Problem(seats=list(neighbours), pupils=[f"p{i}" for i in range(class_size)], neighbours=neighbours)
    assert len(shuffle(problem, random.Random(seed))) == min(class_size, len(neighbours))
