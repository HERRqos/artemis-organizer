# Future features — not building now, don't forget

Deferred items surfaced while reading the code. Cancellation stays
phone/WhatsApp-only (`cancel_appointment` tool) for now — these are what
would be needed to go beyond that later.

## 1. Owner-initiated cancel/reschedule + client notification

**Gap:** she can only cancel/move a client's appointment by editing Google
Calendar directly (outside the bot) — `cancel_appointment`/
`reschedule_appointment` always act on `ctx.sender`'s *own* appointment
(matched by phone number), with no way to target a specific client's
booking. And deleting the event herself notifies nobody — the client just
silently stops getting a reminder; there's no "your appointment was
cancelled" message sent.

**What it would need:**
- A new tool (or small admin action) that takes a target phone number/
  appointment id, not just `ctx.sender` — in `services/engine/app/tools/__init__.py`.
- A trigger for it: either a special command she can text the bot's own
  number (would need `main.py`'s `handle()` to special-case
  `msg.sender == settings.owner_whatsapp`), or a separate small admin
  endpoint.
- Actually notifying the client: call `whatsapp.send_text()` to the
  client's number as part of that flow — doesn't exist today.

## 2. Guest RSVP / detecting a client declining via Calendar

**Gap:** requires domain-wide delegation (Workspace) or Calendly-style
OAuth first, since guests aren't invited at all today (service-account
limitation). Even once guests exist, a decline does NOT free the slot —
`free_slots()` only checks whether an event exists on her calendar, not
attendee `responseStatus`. A guest can't delete her copy of the event
either — only she can actually free the slot.

**What it would need:**
- Domain-wide delegation set up first (separate prerequisite, see
  `calendar.py` notes on this in the learning file).
- Either polling `events().list()` and checking each attendee's
  `responseStatus`, or Google Calendar API push-notification "watch"
  channels to get notified on change.
- A decision on what to DO with a decline: auto-cancel + notify owner, or
  have the bot text the client to confirm before freeing the slot.
- Worth validating demand first: clients interact entirely via WhatsApp
  here, so many may never open a calendar invite email to decline it —
  the existing `cancel_appointment` text path is likely the primary real
  cancellation route regardless.

## 3. Patient database (for monitoring / new vs. returning / status)

**Gap:** no patient/client records exist anywhere. Google Calendar events
(phone+name+note) and Redis session history (ephemeral, 12h) are the only
things resembling "records," and neither is a real client list — no way to
know if someone's a new or returning patient, no status tracking.

**What it would need:**
- `docker-compose.yml` already provisions `postgres` — currently unused,
  exactly the placeholder for this.
- Scope small first: minimal schema answering one concrete question (e.g.
  new vs. returning) rather than a full patient-record system.
- Wire the tool handlers (`_book`, `_cancel`, etc. in
  `services/engine/app/tools/__init__.py`) to also write to that table
  alongside the existing Calendar write.
- If email ever gets collected (needed for guest RSVP above too), this is
  where it would live — this project never asks for email today, only
  phone + name.

## 4. Management UI for FAQ content / office hours

**Gap:** no self-service way for her to update `practice.json` (FAQ
answers) or office-hours env vars. Today every change needs a developer to
edit the file/env var and restart the engine service — matches the
README's own "admin dashboard" line under deliberately deferred.

**Smallest useful version first, not a full admin framework:**
- A small password-protected internal page exposing just two things: an
  editor for `practice.json`'s FAQ entries, and fields for the
  office-hours env vars — writing back to the mounted file/settings and
  triggering a restart.
- Better: refactor `PracticeInfo` (`services/engine/app/tools/practice.py`)
  to re-read the file instead of caching it once at startup, so no
  restart is even needed after an edit.
- Could start even simpler than a web UI at all: she edits a Google Sheet
  herself, and a small script syncs it into `practice.json` — cheaper to
  build than a real page, worth trying before investing in one.
