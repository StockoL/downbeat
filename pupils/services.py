from collections import defaultdict

from .models import PupilFlag


def flag_colours(pupil_ids):
    """{pupil_id: [palette number, ...]} for drawing seat edges. Labels never leave the pupil page."""
    colours = defaultdict(list)
    for pupil_id, colour in PupilFlag.objects.filter(pupil_id__in=pupil_ids).values_list("pupil_id", "flag_type__colour"):
        colours[pupil_id].append(colour)
    return colours


def relationships_among(pupil_ids):
    """[(pupil_a_id, pupil_b_id, kind), ...] for pairs where both pupils are in the given set."""
    from .models import Relationship

    ids = set(pupil_ids)
    return [
        (a, b, kind)
        for a, b, kind in Relationship.objects.filter(pupil_a_id__in=ids, pupil_b_id__in=ids).values_list("pupil_a_id", "pupil_b_id", "kind")
    ]


def placement_rules(pupil_ids):
    """{pupil_id: {rule, ...}} from their flags, ignoring "none"."""
    from .models import PupilFlag

    rules = defaultdict(set)
    for pupil_id, rule in PupilFlag.objects.filter(pupil_id__in=pupil_ids).values_list("pupil_id", "flag_type__placement_rule"):
        if rule != "none":
            rules[pupil_id].add(rule)
    return rules
