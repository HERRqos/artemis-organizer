# Checklist before a real end-to-end test (WhatsApp -> reply)

Everything below has to exist before `docker compose up --build` can
actually hold a conversation. Check off as each is done.

## 1. Meta / WhatsApp (dev test number)

- [ ] Go to developers.facebook.com -> create a Meta App (type: Business)
- [ ] Add the "WhatsApp" product to that app
- [ ] Note the free test number Meta auto-provisions (WhatsApp -> API Setup
      / Getting Started page)
- [ ] Copy the **Phone Number ID** from that same page -> `WHATSAPP_PHONE_NUMBER_ID`
- [ ] Copy the temporary (24h) access token from that page for first tests
      -> `WHATSAPP_TOKEN` (swap for a permanent System User token before
      anything long-running — see below)
- [ ] Add your own phone as a verified test recipient (up to 5 allowed) so
      you can actually message the test number
- [ ] App dashboard -> Settings -> Basic -> copy the App Secret ->
      `META_APP_SECRET`
- [ ] Invent any string yourself for `META_VERIFY_TOKEN` (you pick it, then
      paste the SAME value into Meta's webhook config later)
- [ ] For a permanent token instead of the 24h one: business.facebook.com ->
      Business Settings -> create a System User -> generate its permanent
      token -> `WHATSAPP_TOKEN`

## 2. Google Calendar (service account)

- [ ] Google Cloud Console -> new project -> enable the Calendar API
- [ ] Create a service account in that project
- [ ] Download its JSON credentials file -> save as `secrets/google-sa.json`
      (matches `GOOGLE_CREDENTIALS_FILE=/secrets/google-sa.json` default)
- [ ] Open Google Calendar (personal account is fine) -> share the calendar
      you want to test with -> paste the service account's auto-generated
      email (the `client_email` field inside the JSON) -> permission
      "Make changes to events"
- [ ] Copy that calendar's ID (Settings -> that calendar -> "Integrate
      calendar" -> Calendar ID; `primary` works if it's your own main
      calendar) -> `CALENDAR_ID`

## 3. Anthropic (LLM)

- [ ] console.anthropic.com -> create an API key (separate from any
      claude.ai chat subscription) -> `ANTHROPIC_API_KEY`
- [ ] Confirm billing/credits are enabled on that console account so calls
      don't fail on a payment gate

## 4. Local files

- [ ] `cp .env.example .env`, fill in every value gathered above, plus:
      `OWNER_NAME`, `OWNER_WHATSAPP` (your own number for handoff tests),
      `TIMEZONE`/`OFFICE_OPEN`/`OFFICE_CLOSE`/`OFFICE_DAYS`/`SLOT_MINUTES`
      (defaults are fine for a first test)
- [ ] `mkdir -p secrets` and confirm `secrets/google-sa.json` is inside it
- [ ] Confirm `.env` and `secrets/` are both covered by `.gitignore` before
      going further (don't commit real credentials)

## 5. Running it

- [ ] `docker compose up --build`
- [ ] In a second terminal: `ngrok http 8080`
- [ ] Take the ngrok https URL -> Meta App dashboard -> WhatsApp -> 
      Configuration -> set Callback URL to `<ngrok-url>/webhook` and Verify
      Token to the same `META_VERIFY_TOKEN` you invented above -> Verify
      and save
- [ ] Subscribe the app to the `messages` webhook field for WhatsApp
- [ ] Text the test number from your verified test phone, watch
      `docker compose logs -f webhook engine` for the message flowing
      through
