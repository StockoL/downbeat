"""
The cover PDF: the room layout with names on seats, and nothing else. No flags, badges, notes,
spoken-to or absence; a cover teacher needs to know who sits where.
"""

from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .models import SEAT_HEIGHT, SEAT_WIDTH

MARGIN = 15 * mm
TITLE_SPACE = 14 * mm
FONT = "Helvetica"
TITLE_FONT = "Helvetica-Bold"


def _fit(text, font, size, width):
    """The largest font size up to `size` at which the text fits the width."""
    while size > 5 and stringWidth(text, font, size) > width:
        size -= 0.5
    return size


def cover_pdf(session, seated, unseated):
    """PDF bytes for one session's class in its room."""
    room = session.room
    page_w, page_h = landscape(A4)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.setTitle(f"{session.klass} in {room}")

    pdf.setFont(TITLE_FONT, 16)
    pdf.drawString(MARGIN, page_h - MARGIN - 4 * mm, f"{session.klass} · {room}")

    # Fit the room's canvas into the area below the title, keeping its proportions.
    area_w = page_w - 2 * MARGIN
    area_h = page_h - 2 * MARGIN - TITLE_SPACE - (8 * mm if unseated else 0)
    scale = min(area_w / room.canvas_width, area_h / room.canvas_height)
    origin_x = MARGIN + (area_w - room.canvas_width * scale) / 2
    top = page_h - MARGIN - TITLE_SPACE

    def box(x, y, w, h):
        # Canvas units run down from the top; PDF points run up from the bottom.
        return origin_x + x * scale, top - (y + h) * scale, w * scale, h * scale

    pdf.setLineWidth(0.6)
    pdf.rect(*box(0, 0, room.canvas_width, room.canvas_height))

    seat_w = SEAT_WIDTH * scale
    for seat in room.seats.all():
        x, y, w, h = box(seat.x, seat.y, SEAT_WIDTH, SEAT_HEIGHT)
        pdf.rect(x, y, w, h)
        pupil = seated.get(seat.id)
        if pupil:
            name = str(pupil)
            size = _fit(name, FONT, 11, seat_w - 4)
            pdf.setFont(FONT, size)
            pdf.drawCentredString(x + w / 2, y + h / 2 - size / 3, name)

    if room.teacher_x is not None:
        x, y, _, _ = box(room.teacher_x, room.teacher_y, 0, 0)
        pdf.setFont(FONT, 9)
        pdf.drawCentredString(x, y - 3, "Teacher")

    if unseated:
        pdf.setFont(FONT, 10)
        pdf.drawString(MARGIN, MARGIN, "Not seated: " + ", ".join(str(p) for p in unseated))

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
