# Booking assistant — WhatsApp + Google Calendar

Conversational appointment booking for a appointment organization. LLM tool-calling
over WhatsApp, real availability from Google Calendar, human handoff for
anything that isn't booking or FAQ.

## The two decisions that were open

**WhatsApp access: Meta Cloud API, direct.** No BSP. Twilio would be faster to
wire up, but it wraps the Graph API in its own message format — and phase 2
(Instagram DMs) is *the same Graph API, the same webhook envelope, the same
signature scheme*. Going direct means Instagram is a new `parse_inbound` branch
rather than a second vendor. Cost is €0 at this volume either way.

What you need before it works:
1. Meta Business account + a WhatsApp Business App
2. A phone number **not** already registered to a personal WhatsApp account
3. A System User with a permanent access token (the 24h dev token will bite you)
4. Meta Business Verification — start it early (10 min to ~14 working days).
   Since Nov 2023 it is no longer needed to raise messaging limits, so it may
   not block you at all at one-practice volume.

**Google Calendar: service account + calendar sharing.** She shares her calendar
with the service account's email address, permission "Make changes to events".
Works on a personal Gmail account, no OAuth consent screen, no refresh tokens to
store, rotate or repair at 2am. The one real limitation: a service account can't
invite guests without domain-wide delegation, so the client's name and phone go
into the event body instead of the attendee list. For a solo practice booking
over WhatsApp, nobody misses the calendar invite.

If she ever moves to Google Workspace, the same code works — you'd just be able
to add domain-wide delegation on top if you want invites.

## The one thing that will surprise you

WhatsApp only allows free-form messages inside a **24-hour window** after the
client's last message. A "your appointment is tomorrow" reminder almost always
falls outside it, so it must be a **pre-approved message template** with
variables — not LLM-generated text. `WhatsAppClient.send_template` is already
the reminder path.

Approval is Meta's, not your provider's: automated screening first, human review
only for flagged templates. Usually minutes to a couple of hours, up to 24h;
flagged ones 24–48h. The real time sink is rejection and resubmission, most
often because Meta's classifier reads a Utility template as Marketing. Keep the
reminder literal — "Te recordamos tu cita del {{1}} a las {{2}}" — with no
promotional or padded wording around it.

## Layout

```
shared/assistant_shared/   config, queue abstraction, WhatsApp client, calendar
services/webhook/          FastAPI: verify -> dedupe -> enqueue -> 200
services/engine/           worker: queue -> tool-calling loop -> reply
services/reminder/         worker: 24h-out appointments -> template send
tests/                     run with no Docker, no Redis, no API keys
```

Three portability seams, as planned:

- `services/webhook/app/core.py` is pure functions. `main.py` is a thin FastAPI
  adapter over them; a Lambda handler would be a second adapter, ~15 lines.
- `assistant_shared/queue.py` defines a `Queue` Protocol. `RedisStreamQueue`
  uses consumer groups, so it already has SQS's at-least-once + explicit ack
  semantics. `SqsQueue` is a new class and an env var.
- Calendar, LLM and WhatsApp each live behind one small module. The tool
  registry in `services/engine/app/tools/__init__.py` is the only place that
  knows what tools exist.

## Local dev

```bash
cp .env.example .env          # fill it in
mkdir -p secrets && cp ~/Downloads/service-account.json secrets/google-sa.json
docker compose up --build
```

Expose the webhook for Meta's callback:

```bash
ngrok http 8080
# callback URL: https://<id>.ngrok.app/webhook   verify token: META_VERIFY_TOKEN
```

Run the tests without any of that:

```bash
pip install ./shared pytest && pytest -q
```

## The loop worth reading

`services/engine/app/conversation.py`, ~40 lines:

```
history + message -> LLM -> wants tools? -> run them, append results, ask again
                         -> no tools?    -> that text is the reply
```

Two guards on it: `MAX_TOOL_ROUNDS` caps runaway loops into a handoff, and
`escalation.py` runs *before* the LLM so crisis language never reaches the model
at all. The model also has an `escalate_to_human` tool for the softer cases it
notices itself. Both paths mute the bot for that sender for 24h and ping her
number, so she isn't racing a bot in the same thread.

## Deliberately not built yet

Instagram, Calendly, waitlist, admin dashboard, GDPR tooling. `practice.py` is
keyword matching over a JSON file, not pgvector — the signature is already the
one a retriever will have, so swapping in embeddings later touches one file.
Postgres is in compose but unused; wire it up when the FAQ set outgrows the JSON.

## Next steps, in order

1. Fill `.env`, run compose, POST a fake webhook payload at it (see the test
   fixtures for a valid envelope) and watch the queue → engine → reply path.
2. Get the Meta number + permanent token; point ngrok at it; talk to it.
3. Replace `services/engine/data/practice.json` with her real answers, in her
   words. This is the single biggest quality lever in the whole system.
4. Submit the reminder template for approval.
5. Sit with her and rewrite `prompts.py` together — tone, what she'd never say,
   where she wants to be pulled in.
