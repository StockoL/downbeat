from itertools import count
from types import SimpleNamespace as Seat

from rooms.adjacency import adjacent

# Seats are 80 x 44 canvas units; positions are their top-left corners.


ids = count(1)


def seat(x, y):
    return Seat(id=next(ids), x=x, y=y)


def test_desks_side_by_side_are_neighbours_even_with_a_gap():
    assert adjacent(seat(0, 0), seat(100, 0))  # touching
    assert adjacent(seat(0, 0), seat(160, 0))  # a seat-width gap between


def test_the_seat_in_front_or_behind_is_a_neighbour():
    assert adjacent(seat(0, 0), seat(0, 72))


def test_two_rows_away_is_not():
    assert not adjacent(seat(0, 0), seat(0, 144))


def test_a_diagonal_across_a_gap_is_not():
    assert not adjacent(seat(0, 0), seat(160, 72))


def test_two_desks_along_is_not():
    assert not adjacent(seat(0, 0), seat(320, 0))
    assert not adjacent(seat(0, 0), seat(200, 0))


def test_a_seat_is_not_its_own_neighbour():
    one = seat(0, 0)
    assert not adjacent(one, one)
