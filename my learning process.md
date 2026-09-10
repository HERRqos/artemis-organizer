Webhook
 - Postman is a good analogy — it takes inbound packages from Meta and confirms receipt (that confirmation is literally just the HTTP 200 OK response).
 - I need a Meta Business account, a WhatsApp Business App, and a phone number that isn't already tied to a personal WhatsApp account.
 - it runs as its own Docker container (services/webhook, its own Dockerfile, its own line in docker-compose.yml) — a small always-on process listening for Meta's HTTP requests.
 - Not the same service to other apps, and only Instagram is actually a near-drop-in — because using the same Graph API, same webhook envelope shape, same signature scheme  
 - other apps are different auth, different payload formats, different signature schemes, that needs a genuinely new integration for each. 
 - pattern can be carried over: one dumb, fast endpoint that verifies + dedupes + enqueues, and a separate worker that does the real thinking. the webhook code itself isn't for other apps.
 ? that means another redis for those? or same redis but with a parser to have all in one queue and format?
 - Same Redis, same queue. InboundMessage is already channel-neutral (it has a "channel" field: "whatsapp"|"instagram"), so an Instagram parser would produce the same shape and publish onto the same queue_name — engine already just reads generic messages, it doesn't care which channel produced them.
 ! Correction: the reply side isn't channel-aware yet though — engine's handle() calls whatsapp.send_text() directly, which only knows how to talk to the WhatsApp Graph endpoint. Adding Instagram would need a small dispatch on msg.channel to pick the right outbound client too, not just a new inbound parser.

Engine ("the brain")
 - it reads the message and decides what to do.
 - the LLM does classification and decision-making in one loop (the tool-calling loop), by choosing which tool to call, if any, not the brain.
 - no UI to monitor this today — the README explicitly lists "admin dashboard" under "deliberately not built yet." Right now, monitoring = reading logs (log.info/log.warning calls in the code) — nothing visual.
 - Console logs to see responses. logging.basicConfig(level=logging.INFO), not to a file (confirmed in engine, webhook, reminder — all identical). 
 - In Docker terms, that means to read them with docker compose logs -f engine (or webhook/reminder). 
 - Nothing persists them to disk anywhere right now
 ? what about dev environment, how do i see them? just in the console. i know maybe it is an stupid question.
 - Not stupid — yes, in dev, `docker compose up --build` (without -d) prints every container's logs live, interleaved, right in your terminal. If you ran it detached (-d), use `docker compose logs -f engine` (or webhook/reminder) to stream just that one service's output.
 - it's an API call — llm.py uses anthropic.Anthropic(api_key=...) and calls self._client.messages.create(...) over the network to Anthropic's servers. It's not self-hosted.
 - not self-hosted: it's less about raw speed (a well-provisioned self-hosted model can be fast) and more about not wanting to run/maintain GPU infrastructure for a solo practice's message volume — the API gives you a reliable, well-tested model with zero ops burden, and at this scale the API cost is trivial.
 - a claude.ai chat subscription (Pro/Max) and an Anthropic API key are separate products entirely. This code needs an API key from the Anthropic Console (console.anthropic.com), billed separately on usage. No enterprise tier is required to get one; a standard API account with billing enabled is enough for this use case.
 - you'll need an Anthropic API key (it's pay-as-you-go billing tied to usage, not a flat "subscription"), stored in your .env and read via settings into AnthropicLLM(api_key=...).
 - As the code is written today, there's one ANTHROPIC_API_KEY in Settings, used centrally by engine. If you run this as a hosted service for multiple practices, that one key is yours — you'd see every call and pay for all of it in your own Anthropic Console, and your customers would never touch the key. That's the standard SaaS pattern: you absorb the API cost and price it into what you charge them. The alternative — each customer brings their own key (BYOK) — would put cost and visibility on them instead, but the code as it stands has no per-tenant key support;
 - it's built single-tenant (one deployment, one key, one practice). Multi-tenant would be an actual feature to add later.
 ? in that case will be better to host an LLM?
 - Not really, not at this stage. Self-hosting only pays off once volume is high enough that a GPU server running 24/7 (a fixed cost, whether used or not) beats paying per-message via the API. A solo practice — or even dozens of them as SaaS — stays cheap on the API because you only pay for what's actually sent. Self-hosting also brings back the ops burden (uptime, scaling, patching, model updates) the API was specifically chosen to avoid, plus a real risk that an open model's tool-calling reliability isn't as good as Claude's. It's a later optimization for serious sustained volume, not a starting point.

Reminder
 - it's a loop that periodically checks the calendar for appointments starting in ~24h and sends a reminder to the client via WhatsApp.
 - "Cron-like worker" explained: cron is the classic Unix tool for "run this on a schedule." This isn't literally cron — it's a Python script that never exits: while True: do_the_check(); sleep(300 seconds) (confirmed in reminder/app/main.py, TICK_SECONDS = 300). Same effect as a scheduled job, implemented as an infinite loop inside a long-running container instead.
 - it's a fully separate, independent container running in parallel. sharing nothing but the underlying host's hardware.
 - needs: own container (already in compose), Google Calendar access, and a WhatsApp token — no LLM key needed here, this service never calls Claude at all, it's pure calendar-check + template-send logic.
 - Google Cloud service account. You create a Google Cloud project, enable the Calendar API, create a service account, and download its JSON credentials file (GOOGLE_CREDENTIALS_FILE → secrets/google-sa.json, read via service_account.Credentials.from_service_account_file in calendar.py). Then you share your actual Google Calendar with that service account's auto-generated email address, "Make changes to events." No key string — auth is the JSON file itself.
 ? the user should give me their mail to ad to my google cloud service account? is that also a payed servcie?
 - Backwards, actually: you create the service account (which gets its own auto-generated robot email, like xxx@yyy.iam.gserviceaccount.com), and then SHE shares HER Google Calendar with that email — the same way you'd share a calendar with any other person, via Calendar's own sharing settings, granting "Make changes to events." She never signs up anywhere or gives you anything except clicking "share" once.
 - Not paid: creating a service account and using the Calendar API is free at this volume — Google's free quota is far above what a solo practice (or even several) would generate. A Google Cloud project is required to create the service account, but no billing gets triggered unless you scale into enterprise-level API volume.
 - the permanent token (WHATSAPP_TOKEN) comes from creating a "System User" inside Meta Business Settings, plus a WHATSAPP_PHONE_NUMBER_ID from the WhatsApp product setup in that same business account.
 ? for dev purposes i understand a new one, but for a user they have to give me a new phone number? or is this like a user that can send messages into the other number?
 - The "number not tied to a personal WhatsApp" is the PRACTICE's own dedicated business number, not yours. Each practice registers its own number under its own Meta Business Account as a WhatsApp Business number — that's what their clients text.
 - For dev, you don't burn your own or the practice's number at all: Meta gives you a free test number automatically when you set up the WhatsApp product in Meta for Developers, good enough to send/receive test messages before anything is registered for real.

Redis
 - it's conceptually like RAM: data lives in memory instead of on disk, so reads/writes are extremely fast. Here it's used two ways: (1) as the queue between webhook and engine, and (2) in reminder, as a simple "already sent" marker (marker.set(..., nx=True, ex=...)) so a restart or overlapping check can't send the same reminder twice.
 - webhook answers "got it" instantly, then engine processes and replies whenever it's free to pick the message off the queue. That decoupling is the whole point of the queue.
 - docker-compose.yml runs redis:7-alpine as its own container (port 6379), and webhook/engine/reminder all connect to it over the network via REDIS_URL=redis://redis:6379/0.

Tool definitions
 - they're plain Python dictionaries, defined right in tools/__init__.py as TOOL_SCHEMAS. Each one has a name, a description (written in Spanish — that's
  literally what the LLM reads to decide when to use it), and an input_schema (what parameters it needs). These get handed to the Anthropic API alongside the conversation. 
 - each schema pairs with a real Python function (_check_availability, _book, etc.) that actually calls Google Calendar — the LLM can only request a tool call; the code is what actually does it.
 - it is a dictionary of functions/service that we can use to get info, and the llm can ask us to call them.

Escalation
 - A fail-safe that routes to the human for sensitive topics.
 - it's a list of regex patterns (CRISIS_PATTERNS) matched against the message text (lowercased, accents stripped) using simple keyword/phrase matching. It runs before the LLM is even called, so it's instant and free (no API call).
 - the LLM also has its own escalate_to_human tool, a second, softer safety net for things the keyword list wouldn't catch (e.g., an explicit clinical question or a complaint) — that's the model's own judgment call mid-conversation, versus the hard keyword block that happens before the model ever sees risky text.
 - the sensitive text actually flows: 
    (1) the regex keyword check happens locally, inside own engine container — nothing external involved for that step;
    (2) if it doesn't trip the keyword gate, the raw message still gets sent to Anthropic's API as part of the normal LLM call, since the model needs the text to respond at all; 
    (3) on any escalation, the message is forwarded verbatim to the owner's WhatsApp via notify_owner() — see main.py: f"Handoff ({reason})\nDe: ...\n\n{msg.text}"; 
    (4) it also sits in Redis session history for up to 12h (SessionStore's ttl_seconds).
 - On "how it's clarified": the owner's handoff message literally says why — notify_owner passes "keyword gate" for the regex trigger, or the LLM's own stated escalation_reason for the tool-based one — so she sees "Handoff (keyword gate)" vs. "Handoff (<reason the model gave>)".
 - None of this is encrypted, anonymized, or access-controlled beyond what Redis/Anthropic/Meta provide by default — and the README itself lists "GDPR tooling" under deliberately not built yet. 
 - Since this handles mental-health-adjacent content for someone in Spainsh speaking country, that's a real gap to close before real use, not just a nice-to-have.
 ! this needs more attention.

The 24h mute
 - it's not that the contact gets "redirected to a human" inside WhatsApp automatically — it's that the bot goes silent for that specific contact for 24 hours, and separately, the practice owner's own phone gets pinged so she knows to step in and reply herself. The point is preventing the bot and her from both replying in the same thread at once.
 - Different phones entirely: the bot's WhatsApp Business number (WHATSAPP_PHONE_NUMBER_ID) is what sends messages to both the client and, separately, to the owner's own personal/practice number (OWNER_WHATSAPP) — two different recipients, one sender.
 ? the answer from the user to the users clients goes throw the bot? so the user does not have to give two phones to the user's client? reading down i see it is working together with the block of 24h in that period just the user can send messages to the client, right? but if the user wants to also send somereply or notification that the metting has to be move or delayed?
 - Correct on the first part: the client only ever sees ONE number, the business number — never the owner's personal one.
 ! Correction on the rest: this codebase does NOT give the owner a way to reply to the client through the bot. notify_owner only sends her a message alerting her — it doesn't open a reply channel. In practice she'd have to message the client using Meta's own WhatsApp Manager / Business Suite inbox for that same business number (which she can access directly, outside this code) — the 24h mute just stops the automated code from also butting in while she does that manually. A "meeting needs to move" notification tool isn't built either — today rescheduling only happens when the client asks the LLM for it; a owner-initiated reschedule/notify flow would be a new feature.
 ? for dev practices and understanding a the bots whats is a server and the others are clients? it hast to be one bot per practice? if i use a bot together with my phone to set the dev env i will need another bot number for the practice?
 - "Server" = the whole running backend (webhook+engine+reminder+redis) that owns ONE WhatsApp Business number. "Clients" = anyone texting that number, including the owner's own number when she's just being notified — she's not special infrastructure-wise, just a config value (OWNER_WHATSAPP).
 - Yes, one bot number per practice — Meta ties one WhatsApp Business number to one business profile, and this codebase (as built) assumes one calendar + one owner + one number per deployment.
 - For dev, use Meta's free test number (see above), not your own phone and not the eventual practice's real number — those end up being three different numbers across dev / you / the live practice.

the settings hub - config-py
 - Every environment variable the whole project needs is declared once, here, as a typed Settings dataclass (redis_url, whatsapp_token, anthropic_api_key, office_open/office_close, etc.).
 - load_settings() reads os.environ and builds one Settings object; _req() throws immediately if something required (like META_APP_SECRET) is missing, so a misconfigured deployment fails at startup instead of silently misbehaving later. 
 - The docstring's point matters: nothing else in the codebase touches os.environ directly — every other file receives a Settings object instead.
 ? what is os.environ? operatvie system?
 - Yes, "OS" as in operating system, but scoped to this one detail: os is Python's built-in module for talking to the OS, and os.environ is a dict-like view of that process's environment variables — key/value strings set when the container starts (from .env via docker-compose's env_file). os.environ.get("REDIS_URL") just reads whatever value this specific running process was given for REDIS_URL, nothing systemwide beyond that.
 - That's why the same code can run on Docker Compose today and on Fly/Railway/AWS later without changes — only how Settings gets populated changes, not the code that uses it.
 ? that mean we are not going to create images in docker hub that other plaraforms can just download?
 ! Correction — different topic than it sounds: "portability" here means the CODE doesn't hardcode assumptions tied to one host (no code that only works because it happens to be in Docker) — it's not about publishing images to a registry. Right now docker-compose.yml just builds images locally from each service's Dockerfile every time you run `docker compose up --build`; nothing gets pushed anywhere. You could add a CI step later to build and push images to Docker Hub (or a private registry) for other platforms to pull — that's a separate, optional deployment step this project doesn't do today, but the portable code is what makes adding that later easy.

the Google Calendar wrapper - calendar.py
 - This is what actually implements the tool functions you saw in tools/__init__.py. free_slots() computes your office-hours slots for a date range (respecting OFFICE_OPEN/OFFICE_CLOSE/OFFICE_DAYS/SLOT_MINUTES from settings) and removes any that overlap something already on the calendar (via Google's freebusy query). book() writes a new event —  note the client's phone and name go into the event's description text and a hidden extendedProperties.private.client_phone field, not as an invited guest (that's the service-account limitation the README mentions — no domain-wide delegation, no calendar invite). appointment_for() finds a phone's next booking by searching for that same hidden phone property.
 ? what could we do to overcome this limitation? is there another set up that can cover this limitation? it is because we can not share the appoinment in with the client mail, as attendy if it is a google meet appointment?
 - Yes exactly that reason. Domain-wide delegation lets a service account impersonate a real Google Workspace user ("act as if she created it herself"), and only then can it invite guests / auto-attach Google Meet tied to a real invite. That delegation feature only exists on Google Workspace, not personal Gmail — so the real fix is her moving to Workspace (the README says as much: "same code works, you'd just be able to add domain-wide delegation on top").
 - Workaround without Workspace: generate the Meet link yourself and paste it into the event description (no formal Google invite email, but the client still gets the link — via the WhatsApp confirmation text instead of email, which this system already sends anyway).
 - move()/cancel() patch/delete the event. This is the file that turns "the LLM wants to book 3pm Tuesday" into an actual change on the real calendar.

the outbound message sender - whatsapp.py 
 - Two methods: send_text() for normal free-form replies (only works inside that 24h customer-service window), and send_template() for anything proactive like reminders, which must reference a pre-approved template name instead of arbitrary text. Both just POST to Meta's Graph API (https://graph.facebook.com/<version>/<phone_number_id>/messages) with the permanent token as a bearer header. This is the file both engine (replies) and reminder (24h-out templates) call into — the actual "type on the phone" step.
 ? how is these template approve? i have to send my file to meta and have a tocker that this templete i will use always? i can not send messages directly? how this works? i see the crud url but what is version? phone id i get is the bots number, but how the bot knows to which contact?
 - Approval: you submit the template text (e.g. "Te recordamos tu cita del {{1}} a las {{2}}") once, through Meta's WhatsApp Manager, with a name (matches REMINDER_TEMPLATE, e.g. appointment_reminder) and a category. Meta reviews it (automated first, human only if flagged). Once approved, code references it by that name only — you're not uploading anything per send, just filling the {{1}}/{{2}} values at send time.
 - You CAN send direct free-form text (send_text) any time within 24h of the client's last message — that's normal replies. Reminders are proactive (you're speaking first, unprompted, often a day later) — that specific case is what requires a template; it's WhatsApp's policy, not this code's choice.
 - "version" = GRAPH_API_VERSION (e.g. v21.0), Meta's API version baked into the URL — same idea as any versioned REST API; you pin one so Meta releasing a newer version doesn't silently break your integration.
 - "how does it know which contact": every inbound webhook payload carries the sender's WhatsApp id (msg["from"]), captured as InboundMessage.sender in parse_inbound(). The reply just goes back to that same sender id (whatsapp.send_text(msg.sender, reply)) — the bot doesn't "know" contacts in advance, it just mirrors replies to whoever the incoming message came from.

per-client memory in Redis - session.py
 - Not appointment data (that lives permanently in Google Calendar) — this is just the conversation history and the escalation flag, both temporary. history()/save() store the last max_turns (20) exchanges per sender as JSON in Redis, expiring after 12h (ttl_seconds) — so if a client goes quiet for half a day, the bot "forgets" the conversation and starts fresh next time, which is a deliberate simplicity choice, not a bug. escalate()/is_escalated() are exactly the mute mechanism from your last question — a Redis key with a 24h TTL, nothing more sophisticated.
 ? last max_turns (20) exchanges per sender as JSON in Redis are the conversations you mean stay for 12h? the chats in the whatsapp's bot have to be configurated also to disappear?
 ! Correction — two different things were being mixed together here: Redis only holds THIS BACKEND's own working memory of the conversation, used just so the LLM has context for its next reply. After 12h of silence it expires and the bot "forgets" — starts the next message as a fresh conversation.
 - The actual WhatsApp chat thread the client sees in their own app (and what you'd see in Meta's tools) is stored by Meta/WhatsApp itself, under their own retention rules — completely separate from this Redis TTL, and nothing here deletes or configures that. The client's visible chat history is untouched regardless of what Redis forgets.
 - this one is the one that knows to who answer with whatsapp.py
