"""Thin HTTP adapter around app.core. Swap for a Lambda handler later."""
import json
import logging

from fastapi import FastAPI, Request, Response

from assistant_shared.config import load_settings
from assistant_shared.queue import RedisStreamQueue

from .core import handle_webhook, verify_subscription
from .dedupe import RedisDedupe

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("webhook")

settings = load_settings()
queue = RedisStreamQueue(settings.redis_url, settings.queue_name)
dedupe = RedisDedupe(settings.redis_url)

app = FastAPI(title="booking-assistant-webhook")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/webhook")
def verify(request: Request) -> Response:
    q = request.query_params
    challenge = verify_subscription(
        q.get("hub.mode"), q.get("hub.verify_token"), q.get("hub.challenge"),
        settings.meta_verify_token,
    )
    if challenge is None:
        return Response(status_code=403)
    return Response(content=challenge, media_type="text/plain")


@app.post("/webhook")
async def receive(request: Request) -> Response:
    raw = await request.body()
    status, enqueued = handle_webhook(
        raw_body=raw,
        signature=request.headers.get("x-hub-signature-256"),
        app_secret=settings.meta_app_secret,
        payload_loader=json.loads,
        queue=queue,
        dedupe=dedupe,
    )
    if status == 200 and enqueued:
        log.info("enqueued %d message(s)", enqueued)
    # Always ack fast; retries only help Meta, never us.
    return Response(status_code=status)
