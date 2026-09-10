"""Reminder worker.

Runs every few minutes, finds appointments ~24h out, sends the approved
WhatsApp template. Redis holds a sent-marker so a restart or an overlapping
tick can't double-send.
"""
import logging
import time
from datetime import datetime, timedelta

import redis

from assistant_shared.config import load_settings
from assistant_shared.whatsapp import WhatsAppClient

from assistant_shared.calendar import CalendarService

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("reminder")

TICK_SECONDS = 300
LEAD_HOURS = 24
WINDOW_MINUTES = 5
PHONE_PROP = "client_phone"


def tick(settings, calendar, whatsapp, marker: redis.Redis) -> None:
    now = datetime.now(settings.tz)
    start = now + timedelta(hours=LEAD_HOURS)
    end = start + timedelta(minutes=WINDOW_MINUTES)

    for event in calendar.upcoming_between(start, end):
        event_id = event["id"]
        phone = event.get("extendedProperties", {}).get("private", {}).get(PHONE_PROP)
        if not phone:
            continue
        if not marker.set(f"reminded:{event_id}:24h", "1", nx=True, ex=3 * 24 * 3600):
            continue

        when = datetime.fromisoformat(event["start"]["dateTime"]).astimezone(settings.tz)
        whatsapp.send_template(
            to=phone,
            name=settings.reminder_template,
            params=[when.strftime("%d/%m"), when.strftime("%H:%M")],
        )
        log.info("reminder sent for %s at %s", event_id, when.isoformat())


def main() -> None:
    settings = load_settings()
    calendar = CalendarService(settings)
    whatsapp = WhatsAppClient(settings)
    marker = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    log.info("reminder worker up, lead=%dh tick=%ds", LEAD_HOURS, TICK_SECONDS)

    while True:
        try:
            tick(settings, calendar, whatsapp, marker)
        except Exception:
            log.exception("reminder tick failed")
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
