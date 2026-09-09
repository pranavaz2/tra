"""RFC 5545 iCalendar (.ics) format generator for Travix trips."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
import uuid

from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.trips.domain.entities.trip import Trip


def _escape_ical_text(text_val: Any) -> str:
    """Escape special characters per RFC 5545 Section 3.3.11."""
    if text_val is None:
        return ""
    text_str = str(text_val)
    return (
        text_str.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _format_date(d: date) -> str:
    """Format date as YYYYMMDD."""
    return d.strftime("%Y%m%d")


def _format_datetime_utc(dt: datetime) -> str:
    """Format datetime as YYYYMMDDTHHMMSSZ."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.strftime("%Y%m%dT%H%M%SZ")


class ICalGenerator:
    """Generates RFC 5545 standards-compliant iCalendar files."""

    @classmethod
    def generate(
        cls,
        trip: Trip,
        itinerary: Itinerary | None,
    ) -> str:
        lines: list[str] = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Travix AI//Travix Travel Itinerary//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{_escape_ical_text(trip.title)}",
            f"X-WR-CALDESC:{_escape_ical_text(f'Itinerary for {trip.title}')}",
        ]

        now_str = _format_datetime_utc(datetime.now(UTC))

        if itinerary and itinerary.days:
            for day in sorted(itinerary.days, key=lambda d: d.day_number):
                day_date = day.date
                items = day.items or []

                if not items and day_date:
                    # Emit all-day placeholder event for empty day
                    day_uid = f"day-{day.entity_id}@travix.ai"
                    lines.extend([
                        "BEGIN:VEVENT",
                        f"UID:{day_uid}",
                        f"DTSTAMP:{now_str}",
                        f"DTSTART;VALUE=DATE:{_format_date(day_date)}",
                        f"DTEND;VALUE=DATE:{_format_date(day_date + timedelta(days=1))}",
                        f"SUMMARY:{_escape_ical_text(day.title or f'Day {day.day_number}')}",
                        f"DESCRIPTION:{_escape_ical_text(f'Day {day.day_number} of {trip.title}')}",
                        "STATUS:CONFIRMED",
                        "END:VEVENT",
                    ])
                    continue

                for item in items:
                    item_uid = f"item-{item.entity_id}@travix.ai"
                    summary = str(item.title)
                    desc_parts: list[str] = []
                    if item.description:
                        desc_parts.append(str(item.description))
                    
                    item_type = getattr(item, "item_type", getattr(item, "activity_type", None))
                    if item_type:
                        type_val = item_type.value if hasattr(item_type, "value") else str(item_type)
                        desc_parts.append(f"Type: {type_val}")

                    cost_val = getattr(item, "cost", None) or getattr(item, "estimated_cost", None)
                    if cost_val:
                        if hasattr(cost_val, "amount") and hasattr(cost_val, "currency"):
                            desc_parts.append(f"Cost: {cost_val.amount} {cost_val.currency}")
                        elif getattr(item, "currency", None):
                            desc_parts.append(f"Cost: {cost_val} {item.currency}")
                    description = "\n".join(desc_parts)

                    # Build start/end time
                    event_lines = [
                        "BEGIN:VEVENT",
                        f"UID:{item_uid}",
                        f"DTSTAMP:{now_str}",
                    ]

                    if day_date and item.start_time:
                        start_dt = datetime.combine(day_date, item.start_time, tzinfo=UTC)
                        if item.end_time:
                            end_dt = datetime.combine(day_date, item.end_time, tzinfo=UTC)
                            if end_dt <= start_dt:
                                end_dt = start_dt + timedelta(hours=1)
                        elif getattr(item, "duration_minutes", None):
                            end_dt = start_dt + timedelta(minutes=item.duration_minutes)
                        else:
                            end_dt = start_dt + timedelta(hours=1)

                        event_lines.append(f"DTSTART:{_format_datetime_utc(start_dt)}")
                        event_lines.append(f"DTEND:{_format_datetime_utc(end_dt)}")
                    elif day_date:
                        # All-day activity
                        event_lines.append(f"DTSTART;VALUE=DATE:{_format_date(day_date)}")
                        event_lines.append(f"DTEND;VALUE=DATE:{_format_date(day_date + timedelta(days=1))}")

                    event_lines.append(f"SUMMARY:{_escape_ical_text(summary)}")
                    if description:
                        event_lines.append(f"DESCRIPTION:{_escape_ical_text(description)}")

                    location = getattr(item, "location", None)
                    if location:
                        if isinstance(location, str):
                            event_lines.append(f"LOCATION:{_escape_ical_text(location)}")
                        elif hasattr(location, "address") and location.address:
                            event_lines.append(f"LOCATION:{_escape_ical_text(location.address)}")
                        elif hasattr(location, "name") and location.name:
                            event_lines.append(f"LOCATION:{_escape_ical_text(location.name)}")

                        if hasattr(location, "latitude") and hasattr(location, "longitude") and location.latitude and location.longitude:
                            event_lines.append(f"GEO:{location.latitude:.6f};{location.longitude:.6f}")

                    event_lines.append("STATUS:CONFIRMED")
                    event_lines.append("END:VEVENT")

                    lines.extend(event_lines)

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"
