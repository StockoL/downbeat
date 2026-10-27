"""
A unit's components and feedback codes as a shareable file, so a criteria bank can pass between
teachers. Strands travel by name and are matched (or created) on import.
"""

import json

from django.db import transaction

from .models import Component, FeedbackCode, Strand

FORMAT = "downbeat-criteria"
VERSION = 1


class BadCriteria(ValueError):
    pass


def export(unit):
    components = list(unit.components.select_related("strand", "cumulative_of"))
    position = {c.pk: i for i, c in enumerate(components)}
    return {
        "format": FORMAT,
        "version": VERSION,
        "unit": unit.name,
        "components": [
            {
                "text": c.text, "strand": c.strand.name, "next_step": c.next_step_default,
                "builds_on": position.get(c.cumulative_of_id),
            }
            for c in components
        ],
        "feedback_codes": [
            {"number": f.number, "text": f.text, "action": f.action,
             "component": position.get(f.component_id)}
            for f in unit.feedback_codes.all()
        ],
    }


@transaction.atomic
def import_into(unit, raw):
    """Add a criteria file's components and codes to a unit. Returns (components added, codes added)."""
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise BadCriteria("That isn't a criteria file.") from error
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise BadCriteria("That isn't a Downbeat criteria file.")
    if data.get("version") != VERSION:
        raise BadCriteria("That file is from a different version of Downbeat.")
    rows = data.get("components") or []
    if not isinstance(rows, list) or not all(isinstance(r, dict) and r.get("text") and r.get("strand") for r in rows):
        raise BadCriteria("Each component needs its text and a strand.")

    start = unit.components.count()
    made = []
    for i, row in enumerate(rows):
        strand, _ = Strand.objects.get_or_create(name=str(row["strand"])[:60])
        made.append(Component.objects.create(
            unit=unit, order=start + i, text=str(row["text"])[:200], strand=strand,
            next_step_default=str(row.get("next_step") or "")[:200],
        ))
    for component, row in zip(made, rows, strict=True):
        builds_on = row.get("builds_on")
        if isinstance(builds_on, int) and 0 <= builds_on < len(made) and made[builds_on] is not component:
            component.cumulative_of = made[builds_on]
            component.save(update_fields=["cumulative_of", "updated_at"])

    codes = 0
    taken = set(unit.feedback_codes.values_list("number", flat=True))
    for row in data.get("feedback_codes") or []:
        if not isinstance(row, dict) or not isinstance(row.get("number"), int) or not row.get("text") or row["number"] in taken:
            continue
        linked = row.get("component")
        FeedbackCode.objects.create(
            unit=unit, number=row["number"], text=str(row["text"])[:200], action=str(row.get("action") or "")[:200],
            component=made[linked] if isinstance(linked, int) and 0 <= linked < len(made) else None,
        )
        taken.add(row["number"])
        codes += 1
    return len(made), codes
