"""Google Calendar service module.

Auth: a service account whose email your friend shares her calendar
with ("Make changes to events"). No OAuth consent screen, no refresh
tokens to store or rotate. Caveat: a service account on a personal
Google account cannot invite guests, so the client's details go in the
event body instead of as an attendee.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

from assistant_shared.config import Settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]
PHONE_PROP = "client_phone"


@dataclass(frozen=True)
class Appointment:
    event_id: str
    start: datetime
    summary: str


class CalendarService:
    def __init__(self, settings: Settings):
        creds = service_account.Credentials.from_service_account_file(
            settings.google_credentials_file, scopes=SCOPES
        )
        self._api = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._cal = settings.calendar_id
        self._s = settings

    # ---------- reads ----------

    def free_slots(self, day_from: datetime, day_to: datetime) -> list[datetime]:
        """Office-hours slots in [day_from, day_to] with nothing booked."""
        busy = self._busy(day_from, day_to)
        slots: list[datetime] = []
        now = datetime.now(self._s.tz)
        day = day_from.date()
        while day <= day_to.date():
            if day.weekday() in self._s.office_days:
                for slot in self._day_slots(day):
                    end = slot + timedelta(minutes=self._s.slot_minutes)
                    if slot <= now:
                        continue
                    if any(b0 < end and slot < b1 for b0, b1 in busy):
                        continue
                    slots.append(slot)
            day += timedelta(days=1)
        return slots

    def appointment_for(self, phone: str) -> Appointment | None:
        """Next upcoming appointment belonging to this phone number."""
        resp = (
            self._api.events()
            .list(
                calendarId=self._cal,
                privateExtendedProperty=f"{PHONE_PROP}={phone}",
                timeMin=datetime.now(self._s.tz).isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=1,
            )
            .execute()
        )
        items = resp.get("items", [])
        if not items:
            return None
        ev = items[0]
        return Appointment(
            event_id=ev["id"],
            start=datetime.fromisoformat(ev["start"]["dateTime"]),
            summary=ev.get("summary", ""),
        )

    def upcoming_between(self, start: datetime, end: datetime) -> list[dict]:
        return (
            self._api.events()
            .list(
                calendarId=self._cal,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
            .get("items", [])
        )

    # ---------- writes ----------

    def book(self, start: datetime, phone: str, client_name: str, note: str = "") -> Appointment:
        end = start + timedelta(minutes=self._s.slot_minutes)
        body = {
            "summary": f"Sesión — {client_name}",
            "description": f"Reservado por WhatsApp.\nTeléfono: {phone}\n{note}".strip(),
            "start": {"dateTime": start.isoformat(), "timeZone": self._s.timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": self._s.timezone},
            "extendedProperties": {"private": {PHONE_PROP: phone}},
        }
        ev = self._api.events().insert(calendarId=self._cal, body=body).execute()
        return Appointment(ev["id"], start, ev.get("summary", ""))

    def move(self, event_id: str, new_start: datetime) -> Appointment:
        end = new_start + timedelta(minutes=self._s.slot_minutes)
        ev = (
            self._api.events()
            .patch(
                calendarId=self._cal,
                eventId=event_id,
                body={
                    "start": {"dateTime": new_start.isoformat(), "timeZone": self._s.timezone},
                    "end": {"dateTime": end.isoformat(), "timeZone": self._s.timezone},
                },
            )
            .execute()
        )
        return Appointment(ev["id"], new_start, ev.get("summary", ""))

    def cancel(self, event_id: str) -> None:
        self._api.events().delete(calendarId=self._cal, eventId=event_id).execute()

    # ---------- internals ----------

    def _busy(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        resp = (
            self._api.freebusy()
            .query(
                body={
                    "timeMin": start.isoformat(),
                    "timeMax": end.isoformat(),
                    "timeZone": self._s.timezone,
                    "items": [{"id": self._cal}],
                }
            )
            .execute()
        )
        periods = resp["calendars"][self._cal].get("busy", [])
        return [
            (datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"]))
            for p in periods
        ]

    def _day_slots(self, day) -> list[datetime]:
        open_h, open_m = (int(x) for x in self._s.office_open.split(":"))
        close_h, close_m = (int(x) for x in self._s.office_close.split(":"))
        cursor = datetime.combine(day, time(open_h, open_m), tzinfo=self._s.tz)
        closing = datetime.combine(day, time(close_h, close_m), tzinfo=self._s.tz)
        step = timedelta(minutes=self._s.slot_minutes)
        out = []
        while cursor + step <= closing:
            out.append(cursor)
            cursor += step
        return out
