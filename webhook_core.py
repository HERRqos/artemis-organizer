"""Pure webhook logic — no FastAPI, no Redis types, no PaaS.

Every function here is callable from a container process today or a
Lambda handler later. main.py is the only file that knows about HTTP.
"""
import hashlib
import hmac
from typing import Any, Callable, Protocol

from assistant_shared.models import InboundMessage
from assistant_shared.queue import Queue


class Dedupe(Protocol):
    def seen(self, key: str) -> bool: ...


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Meta sends X-Hub-Signature-256: sha256=<hex hmac of the raw body>."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def parse_inbound(payload: dict[str, Any]) -> list[InboundMessage]:
    """Flatten the Graph webhook envelope into channel-neutral messages.

    Ignores everything that is not an inbound text message: status
    callbacks (sent/delivered/read), reactions, media, unknown fields.
    """
    out: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            profiles = {
                c.get("wa_id"): c.get("profile", {}).get("name", "")
                for c in value.get("contacts", [])
            }
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                sender = msg.get("from", "")
                out.append(
                    InboundMessage(
                        message_id=msg["id"],
                        channel="whatsapp",
                        sender=sender,
                        text=msg["text"]["body"],
                        timestamp=int(msg.get("timestamp", 0)),
                        profile_name=profiles.get(sender, ""),
                    )
                )
    return out


def handle_webhook(
    *,
    raw_body: bytes,
    signature: str | None,
    app_secret: str,
    payload_loader: Callable[[bytes], dict[str, Any]],
    queue: Queue,
    dedupe: Dedupe,
) -> tuple[int, int]:
    """Verify, dedupe, enqueue, done. Returns (http_status, n_enqueued).

    Meta retries aggressively on anything slower than a few seconds, so
    this must never call the LLM or Google. It only puts work on a queue.
    """
    if not verify_signature(app_secret, raw_body, signature):
        return 403, 0

    enqueued = 0
    for message in parse_inbound(payload_loader(raw_body)):
        if dedupe.seen(message.message_id):
            continue
        queue.publish(message.to_dict())
        enqueued += 1
    return 200, enqueued


def verify_subscription(
    mode: str | None, token: str | None, challenge: str | None, verify_token: str
) -> str | None:
    """GET handshake Meta performs once when you register the callback URL."""
    if mode == "subscribe" and token == verify_token:
        return challenge
    return None
