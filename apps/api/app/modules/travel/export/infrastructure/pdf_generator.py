"""Pure Python PDF 1.4 vector generator for Travix itineraries."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.trips.domain.entities.trip import Trip


def _escape_pdf_text(text_val: Any) -> str:
    """Escape parentheses and backslashes for PDF string literals."""
    if text_val is None:
        return ""
    text_str = str(text_val)
    return (
        text_str.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


class SimplePdfDocument:
    """Lightweight pure-Python PDF 1.4 document builder."""

    def __init__(self, page_width: float = 595.28, page_height: float = 841.89) -> None:
        self.width = page_width
        self.height = page_height
        self.pages: list[str] = []
        self._current_page_stream: list[str] = []

    def new_page(self) -> None:
        if self._current_page_stream:
            self.pages.append("\n".join(self._current_page_stream))
            self._current_page_stream = []

    def finish_page(self) -> None:
        if self._current_page_stream:
            self.pages.append("\n".join(self._current_page_stream))
            self._current_page_stream = []

    def set_fill_color(self, r: float, g: float, b: float) -> None:
        self._current_page_stream.append(f"{r:.3f} {g:.3f} {b:.3f} rg")

    def set_stroke_color(self, r: float, g: float, b: float) -> None:
        self._current_page_stream.append(f"{r:.3f} {g:.3f} {b:.3f} RG")

    def draw_rect(self, x: float, y: float, w: float, h: float, fill: bool = True, stroke: bool = False) -> None:
        self._current_page_stream.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill and stroke:
            self._current_page_stream.append("B")
        elif fill:
            self._current_page_stream.append("f")
        elif stroke:
            self._current_page_stream.append("S")

    def draw_line(self, x1: float, y1: float, x2: float, y2: float, width: float = 1.0) -> None:
        self._current_page_stream.append(f"{width:.2f} w")
        self._current_page_stream.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def draw_text(
        self,
        text_str: str,
        x: float,
        y: float,
        font: str = "F1",
        size: float = 10.0,
        r: float = 0.1,
        g: float = 0.1,
        b: float = 0.1,
    ) -> None:
        escaped = _escape_pdf_text(text_str)
        self.set_fill_color(r, g, b)
        self._current_page_stream.append("BT")
        self._current_page_stream.append(f"/{font} {size:.2f} Tf")
        self._current_page_stream.append(f"{x:.2f} {y:.2f} Td")
        self._current_page_stream.append(f"({escaped}) Tj")
        self._current_page_stream.append("ET")

    def build(self) -> bytes:
        self.finish_page()
        if not self.pages:
            self.new_page()
            self.finish_page()

        num_pages = len(self.pages)
        objects: list[str] = []

        # 1 0 obj: Catalog
        objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")

        # 2 0 obj: Pages
        page_refs = [f"{3 + i * 2} 0 R" for i in range(num_pages)]
        objects.append(
            f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {num_pages} >>\nendobj"
        )

        # Standard font objects: Font F1 (Helvetica), Font F2 (Helvetica-Bold)
        font1_obj_num = 3 + num_pages * 2
        font2_obj_num = font1_obj_num + 1
        font3_obj_num = font2_obj_num + 1

        for i, stream_content in enumerate(self.pages):
            page_obj_num = 3 + i * 2
            content_obj_num = page_obj_num + 1
            stream_bytes = stream_content.encode("utf-8")
            stream_len = len(stream_bytes)

            # Page obj
            objects.append(
                f"{page_obj_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Contents {content_obj_num} 0 R /Resources << /Font << /F1 {font1_obj_num} 0 R /F2 {font2_obj_num} 0 R /F3 {font3_obj_num} 0 R >> >> >>\nendobj"
            )
            # Content obj
            objects.append(
                f"{content_obj_num} 0 obj\n<< /Length {stream_len} >>\nstream\n{stream_content}\nendstream\nendobj"
            )

        objects.append(f"{font1_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj")
        objects.append(f"{font2_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj")
        objects.append(f"{font3_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>\nendobj")

        out = BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets = [0]
        for obj in objects:
            offsets.append(out.tell())
            out.write(obj.encode("utf-8"))
            out.write(b"\n")

        xref_pos = out.tell()
        out.write(f"xref\n0 {len(offsets)}\n".encode("utf-8"))
        out.write(b"0000000000 65535 f \n")
        for pos in offsets[1:]:
            out.write(f"{pos:010d} 00000 n \n".encode("utf-8"))

        total_objs = len(offsets)
        trailer = (
            f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        )
        out.write(trailer.encode("utf-8"))
        return out.getvalue()


class PdfGenerator:
    """Renders high-quality PDF itineraries for Travix trips."""

    @classmethod
    def generate(
        cls,
        trip: Trip,
        itinerary: Itinerary | None,
        budget: TripBudget | None = None,
    ) -> bytes:
        doc = SimplePdfDocument()
        margin_x = 45.0
        y = 800.0

        # --- Header Banner ---
        doc.set_fill_color(0.06, 0.09, 0.16)  # Dark slate header
        doc.draw_rect(0, 720, 595.28, 121.89, fill=True)

        doc.set_fill_color(0.39, 0.40, 0.95)  # Indigo accent bar
        doc.draw_rect(margin_x, 805, 40, 4, fill=True)

        doc.draw_text("TRAVIX AI ITINERARY", margin_x, 788, font="F2", size=10, r=0.51, g=0.55, b=0.98)
        doc.draw_text(str(trip.title), margin_x, 755, font="F2", size=22, r=1.0, g=1.0, b=1.0)

        date_str = "Dates: Not set"
        if trip.date_range and trip.date_range.departure_date:
            dep = trip.date_range.departure_date.strftime("%b %d, %Y")
            ret = trip.date_range.return_date.strftime("%b %d, %Y") if trip.date_range.return_date else "Flexible"
            date_str = f"Dates: {dep} - {ret}"
        doc.draw_text(date_str, margin_x, 735, font="F1", size=10, r=0.75, g=0.80, b=0.90)

        status_text = f"Status: {trip.status.value.upper()}"
        doc.draw_text(status_text, 440, 735, font="F2", size=10, r=0.30, g=0.75, b=0.55)

        y = 690.0

        # --- Budget Overview Box ---
        if budget:
            doc.set_fill_color(0.96, 0.97, 0.99)
            doc.draw_rect(margin_x, y - 45, 505.28, 48, fill=True)
            doc.set_stroke_color(0.85, 0.88, 0.94)
            doc.draw_rect(margin_x, y - 45, 505.28, 48, fill=False, stroke=True)

            doc.draw_text("Budget Summary", margin_x + 12, y - 12, font="F2", size=10, r=0.2, g=0.25, b=0.35)

            limit_str = f"Limit: {budget.limit.amount} {budget.limit.currency}"
            spent_str = f"Spent: {budget.total_spent.amount} {budget.limit.currency}"
            rem_str = f"Remaining: {budget.remaining_budget.amount} {budget.limit.currency}"

            doc.draw_text(limit_str, margin_x + 12, y - 30, font="F1", size=9, r=0.3, g=0.35, b=0.45)
            doc.draw_text(spent_str, margin_x + 180, y - 30, font="F1", size=9, r=0.3, g=0.35, b=0.45)
            doc.draw_text(rem_str, margin_x + 350, y - 30, font="F2", size=9, r=0.1, g=0.6, b=0.3)

            y -= 65.0

        # --- Itinerary Days & Schedule ---
        doc.draw_text("Trip Schedule", margin_x, y, font="F2", size=14, r=0.1, g=0.15, b=0.25)
        doc.set_stroke_color(0.88, 0.90, 0.94)
        doc.draw_line(margin_x, y - 6, 550, y - 6, width=1.0)
        y -= 25.0

        if not itinerary or not itinerary.days:
            doc.draw_text("No itinerary days scheduled yet.", margin_x, y, font="F3", size=10, r=0.5, g=0.55, b=0.6)
        else:
            for day in sorted(itinerary.days, key=lambda d: d.day_number):
                if y < 120:
                    doc.new_page()
                    y = 780

                # Day Header
                day_title = f"Day {day.day_number}" + (f": {day.title}" if day.title else "")
                day_date_str = day.date.strftime("%A, %B %d, %Y") if day.date else ""

                doc.set_fill_color(0.24, 0.27, 0.40)
                doc.draw_rect(margin_x, y - 18, 505.28, 20, fill=True)
                doc.draw_text(day_title, margin_x + 8, y - 12, font="F2", size=10, r=1.0, g=1.0, b=1.0)
                if day_date_str:
                    doc.draw_text(day_date_str, 380, y - 12, font="F1", size=9, r=0.9, g=0.92, b=0.98)

                y -= 30.0

                items = day.items or []
                if not items:
                    doc.draw_text("No activities planned for this day.", margin_x + 12, y, font="F3", size=9, r=0.5, g=0.55, b=0.6)
                    y -= 20.0
                else:
                    for item in items:
                        if y < 90:
                            doc.new_page()
                            y = 780

                        time_str = item.start_time.strftime("%H:%M") if item.start_time else "Anytime"
                        if item.end_time and item.start_time:
                            time_str += f" - {item.end_time.strftime('%H:%M')}"

                        # Activity line
                        doc.draw_text(time_str, margin_x + 10, y, font="F2", size=9, r=0.39, g=0.40, b=0.95)
                        doc.draw_text(item.title, margin_x + 95, y, font="F2", size=9, r=0.12, g=0.15, b=0.22)

                        cost_val = getattr(item, "cost", None) or getattr(item, "estimated_cost", None)
                        if cost_val:
                            if hasattr(cost_val, "amount") and hasattr(cost_val, "currency"):
                                cost_str = f"{cost_val.amount} {cost_val.currency}"
                                doc.draw_text(cost_str, 470, y, font="F1", size=8, r=0.2, g=0.55, b=0.35)
                            elif getattr(item, "currency", None):
                                cost_str = f"{cost_val} {item.currency}"
                                doc.draw_text(cost_str, 470, y, font="F1", size=8, r=0.2, g=0.55, b=0.35)

                        y -= 13.0

                        loc_val = getattr(item, "location", None)
                        if loc_val:
                            loc_str = ""
                            if isinstance(loc_val, str):
                                loc_str = loc_val
                            elif hasattr(loc_val, "address") and loc_val.address:
                                loc_str = loc_val.address
                            elif hasattr(loc_val, "name") and loc_val.name:
                                loc_str = loc_val.name
                            if loc_str:
                                doc.draw_text(f"Location: {loc_str[:60]}", margin_x + 95, y, font="F1", size=8, r=0.45, g=0.50, b=0.58)
                                y -= 12.0

                        if getattr(item, "description", None):
                            doc.draw_text(f"Note: {str(item.description)[:75]}", margin_x + 95, y, font="F3", size=8, r=0.45, g=0.50, b=0.58)
                            y -= 12.0

                        y -= 4.0

                y -= 12.0

        # Footer on each page
        doc.draw_text("Generated by Travix AI — Your Intelligent Travel Companion", margin_x, 30, font="F3", size=8, r=0.55, g=0.60, b=0.68)
        return doc.build()
