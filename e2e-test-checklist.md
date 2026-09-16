# Checklist before a real end-to-end test (WhatsApp -> reply)

Everything below has to exist before `docker compose up --build` can
actually hold a conversation. Check off as each is done.

## 1. Meta / WhatsApp (dev test number)

- [x] Meta Business Portfolio created first (newer flow requires this
      before the app): `Arty-BSS`, at business.facebook.com
- [x] developers.facebook.com -> Create App -> newer flow asks for a name
      + "use case" instead of a raw app type
      - App name: `Arty_Orga`
      - Use case: **Business messaging** (covers WhatsApp API access)
      - Checked both WhatsApp and Instagram as products — harmless to
        have both attached even though only WhatsApp gets configured now
      - Linked the app to the `Arty-BSS` business portfolio
      - Path chosen: **"Try it out"** (dev/test, no business verification
        needed) + integration type **"API"** (NOT "become a partner" —
        that's Meta's Business-Solution-Provider path for managing many
        clients' numbers, i.e. the multi-tenant SaaS direction logged in
        future-features-notes.md, not needed now)
- [x] Note the free test number Meta auto-provisioned (WhatsApp -> API
      Setup / Getting Started page)
- [x] Copied the **Phone Number ID** -> `WHATSAPP_PHONE_NUMBER_ID`
- [x] Copied the temporary (24h) access token -> `WHATSAPP_TOKEN` (swap
      for a permanent System User token before anything long-running —
      see below)
- [x] Add your own phone as a verified test recipient (up to 5 allowed) so
      you can actually message the test number
      - Found under: developers.facebook.com dashboard -> "Customize the
        Connect with customers through WhatsApp use case" (the old "API
        Setup" tab got folded into this use-case flow) -> "To" dropdown ->
        "Manage phone number list" -> add + verify via code. NOT under
        business.facebook.com's WhatsApp Manager (that's for managing
        already-registered numbers/templates, not adding test recipients)
      - Already done earlier, while still on the temporary 24h token —
        confirmed working, received a test text
- [x] App dashboard -> App settings -> Basic -> "Show" App Secret
      (re-enter Facebook password) -> `META_APP_SECRET`
- [x] `META_VERIFY_TOKEN` — NOT fetched from Meta, invented yourself, then
      the exact same string gets pasted into Meta's webhook config later.
      **Correct/cybersecure way to generate it:** use Python's `secrets`
      module (cryptographically secure random generator — plain `random`
      is NOT safe for anything security-related):
      ```
      python -c "import secrets; print(secrets.token_urlsafe(32))"
      ```
      Why this matters even for a "just a handshake" string:
      `verify_subscription()` only checks that `mode=="subscribe"` and the
      token matches — a guessable/memorable phrase could eventually be
      guessed or brute-forced by someone probing your webhook URL; a long
      random value makes guessing computationally **infeasible, not
      impossible** (there's no such thing as literally impossible to
      guess — just astronomically unlikely with enough entropy).
- [x] For a permanent token instead of the 24h one: business.facebook.com ->
      Business Settings -> create a System User -> generate its permanent
      token -> `WHATSAPP_TOKEN`
      - Two SEPARATE grants needed, not one: (1) Business Settings ->
        Accounts -> Apps -> select `Arty_Orga` -> assign the system user
        full/Admin access to the APP itself (lets it generate/manage
        tokens for it); (2) system user -> Add Assets -> WhatsApp Accounts
        -> Full control on the WhatsApp Business Account (lets tokens
        actually send messages). Both are required.
      - Permissions to select when generating the token:
        `whatsapp_business_messaging` + `whatsapp_business_management`,
        expiration set to Never
      - Reload the Business Settings page after assigning access —
        changes don't always show up live without a refresh

## 2. Google Calendar (service account)

- [x] Google Cloud Console -> new project -> enable the Calendar API
      - Project: `arty-organizer` (console.cloud.google.com, via
        APIs & Services -> Library -> searched "Google Calendar API" -> Enable)
      - Note: dismissed the "Try for free" billing trial prompt during
        project creation, didn't need to accept it just to enable the API
      - Note: quick-access tiles on the welcome walkthrough (Gemini API key,
        VM, BigQuery, deploy app, storage bucket) are unrelated, ignored them
- [x] Create a service account in that project
      - APIs & Services -> Credentials -> Create Credentials -> Service account
      - "What data will you be accessing?" -> chose **Application data**
        (NOT "User data" — that would create an OAuth client instead, which
        this project deliberately avoids)
      - Account name: `arty-organizer`
      - Service account email (this is what gets shared with the calendar):
        `arty-organizer@arty-organizer.iam.gserviceaccount.com`
      - Skipped the optional "grant access" role screens — not needed, its
        access comes from calendar sharing, not IAM roles
      - Calendar API service enabled under: `calendar-json.googleapis.com`
- [x] Download its JSON credentials file -> save as `secrets/google-sa.json`
      (matches `GOOGLE_CREDENTIALS_FILE=/secrets/google-sa.json` default)
      - Service account -> Keys tab -> Add Key -> Create new key -> JSON
      - Downloaded filename didn't match the default (`arty-organizer-<hash>.json`)
        -> renamed to `google-sa.json` to match `GOOGLE_CREDENTIALS_FILE` default
- [x] Open Google Calendar (personal account is fine) -> share the calendar
      you want to test with -> paste the service account's email above
      (`arty-organizer@arty-organizer.iam.gserviceaccount.com`) -> permission
      "Make changes to events"
- [x] Copy that calendar's ID (Settings -> that calendar -> "Integrate
      calendar" -> Calendar ID; `primary` works if it's your own main
      calendar) -> `CALENDAR_ID`
      - Created a dedicated secondary calendar for testing (`test01`)
        instead of using the main personal calendar — ID ends in
        `@group.calendar.google.com` (not `.calendar.google.com`)

## 3. Anthropic (LLM)

- [x] console.anthropic.com -> create an API key (separate from any
      claude.ai chat subscription) -> `ANTHROPIC_API_KEY`
- [x] Confirm billing/credits are enabled on that console account so calls
      don't fail on a payment gate
      - Set a spend limit at the WORKSPACE level (not org-wide), so a bug
        can't run up unrelated costs: workspace cap $2, monthly cap $5
      - Note: paying/adding billing here is normal and expected for API
        usage — separate from any claude.ai chat subscription entirely
- [x] Key generated and saved into `.env` as `ANTHROPIC_API_KEY`

## 4. Local files

- [x] `cp .env.example .env`, fill in every value gathered above, plus:
      `OWNER_NAME`, `OWNER_WHATSAPP` (your own number for handoff tests),
      `TIMEZONE`/`OFFICE_OPEN`/`OFFICE_CLOSE`/`OFFICE_DAYS`/`SLOT_MINUTES`
      (defaults are fine for a first test)
      - `OWNER_WHATSAPP` = own real number; `OWNER_NAME` = a pseudonym
- [x] `mkdir -p secrets` and confirm `secrets/google-sa.json` is inside it
- [x] Confirm `.env` and `secrets/` are both covered by `.gitignore` before
      going further (don't commit real credentials)

## 5. Running it

- [x] `docker compose up --build`
      - Hit a real bug here: engine kept crash-looping with
        `redis.exceptions.TimeoutError` on `queue.consume()`'s blocking
        `XREADGROUP ... BLOCK 5000`. Root cause: the redis-py client's own
        read deadline matched the server's BLOCK window with no margin,
        so any real network latency (Docker Desktop/WSL2 virtualized
        network) made it time out before the server's reply arrived —
        deterministic every run, not flaky. Fixed in
        `shared/assistant_shared/queue.py` by adding
        `socket_keepalive=True, socket_timeout=None` to the Redis client
        construction (rebuild required — `shared/` is baked into the
        image, not bind-mounted). Full writeup logged in the learning file.
      - webhook/redis/postgres get a `ports:` mapping in
        `docker-compose.yml`; engine/reminder don't, on purpose — only
        something that accepts INCOMING connections needs one, and those
        two are pure outbound background workers.
      - Confirmed stable after the fix — engine stayed up.
- [ ] In a second terminal: `ngrok http 8080`
- [ ] Take the ngrok https URL -> Meta App dashboard -> WhatsApp -> 
      Configuration -> set Callback URL to `<ngrok-url>/webhook` and Verify
      Token to the same `META_VERIFY_TOKEN` you invented above -> Verify
      and save
- [ ] Subscribe the app to the `messages` webhook field for WhatsApp
- [ ] Text the test number from your verified test phone, watch
      `docker compose logs -f webhook engine` for the message flowing
      through
