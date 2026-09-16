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

## 4. Management console — settings + patient organization/triage

**Gap:** no self-service way for her to update `practice.json` (FAQ
answers) or office-hours env vars — every change needs a developer to
edit the file/env var and restart the engine service (matches the
README's own "admin dashboard" line under deliberately deferred). Fuller
vision, once patient data exists (item 3): a place for her to see/organize
her patients — flag priority or risk level, review who escalated and why
(ties into the Escalation section's `reason`/keyword-gate vs. LLM-tool
distinction) — not just edit config.

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
- The patient-organization/risk-flagging layer depends on item 3 (patient
  database) existing first — it's a view on top of that data, not a
  separate feature to build standalone.

## 5. Multi-tenant SaaS architecture (one deployment, many therapists)

**Goal:** instead of a separate `docker compose up` stack per therapist,
one running deployment serves many, each managed through the console
above instead of redeployment.

**Gap:** `Settings` (`config.py`) is loaded ONCE, globally, at process
startup — one calendar, one owner, one set of office hours, one WhatsApp
number, for the life of the process. Nothing today identifies *which*
therapist an inbound message is for.

**What it would need:**
- Meta's real webhook payload carries `value.metadata.phone_number_id` —
  not currently read by `parse_inbound()` — telling you which registered
  number received the message. That becomes the tenant-routing key (Meta
  supports multiple numbers under one Business/App).
- A tenant/practice table (the same unused `postgres` from item 3): one
  row per therapist — `calendar_id`, office hours, `owner_whatsapp`, FAQ
  content, `phone_number_id`.
- `Settings` becomes a per-message lookup (by `phone_number_id`) instead
  of a fixed object built once in `main()`.
- Stays simple: one shared service account can already be shared by any
  number of therapists' calendars (only `calendar_id` needs to be
  per-tenant, not the credential) — same for the Anthropic key, which can
  likely stay shared/yours (the SaaS-absorbs-cost model already noted
  under Engine in the learning file) rather than per-tenant. One shared
  Redis queue is also fine — no need to multiply infrastructure, just
  route by the payload's `phone_number_id` once picked up.
- The genuinely hard part: getting multiple therapists' WhatsApp numbers
  registered under a setup managed centrally — Meta has a formal path for
  this (a "Tech Provider"-style flow for managing numbers on behalf of
  clients), meaningfully more involved than the current single-number dev
  setup.

**Sequencing:** get a single-tenant end-to-end test fully working first —
this architecture is a rethink for later, not a blocker on testing now.
