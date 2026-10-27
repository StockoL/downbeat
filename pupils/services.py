from collections import defaultdict

from .models import PupilFlag


def flag_colours(pupil_ids):
    """{pupil_id: [palette number, ...]} for drawing seat edges. Labels never leave the pupil page."""
    colours = defaultdict(list)
    for pupil_id, colour in PupilFlag.objects.filter(pupil_id__in=pupil_ids).values_list("pupil_id", "flag_type__colour"):
        colours[pupil_id].append(colour)
    return colours
