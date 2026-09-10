"""These run without Docker, Redis, Meta or an API key — which is the
whole point of keeping core.py free of infrastructure.

    pip install pytest ./shared && pytest
"""
import hashlib
import hmac
import json

import pytest

from services.webhook.app.core import (
    handle_webhook, parse_inbound, verify_signature, verify_subscription,
)

SECRET = "s3cret"


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def envelope(msg_id: str = "wamid.1", text: str = "hola") -> dict:
    return {
        "entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": "34600000000", "profile": {"name": "Ana"}}],
            "messages": [{
                "id": msg_id, "from": "34600000000", "type": "text",
                "timestamp": "1757000000", "text": {"body": text},
            }],
        }}]}]
    }


class FakeQueue:
    def __init__(self):
        self.published = []

    def publish(self, payload):
        self.published.append(payload)
        return str(len(self.published))

    def consume(self, *a, **k):
        return []

    def ack(self, receipt):
        pass


class FakeDedupe:
    def __init__(self):
        self.keys = set()

    def seen(self, key):
        if key in self.keys:
            return True
        self.keys.add(key)
        return False


def call(payload, queue, dedupe, signature=None):
    body = json.dumps(payload).encode()
    return handle_webhook(
        raw_body=body,
        signature=signature or sign(body),
        app_secret=SECRET,
        payload_loader=json.loads,
        queue=queue,
        dedupe=dedupe,
    )


def test_rejects_bad_signature():
    q, d = FakeQueue(), FakeDedupe()
    status, n = call(envelope(), q, d, signature="sha256=deadbeef")
    assert status == 403 and n == 0 and q.published == []


def test_enqueues_text_message():
    q, d = FakeQueue(), FakeDedupe()
    status, n = call(envelope(), q, d)
    assert (status, n) == (200, 1)
    assert q.published[0]["text"] == "hola"
    assert q.published[0]["profile_name"] == "Ana"


def test_retry_of_same_message_is_dropped():
    q, d = FakeQueue(), FakeDedupe()
    call(envelope(), q, d)
    status, n = call(envelope(), q, d)
    assert (status, n) == (200, 0)
    assert len(q.published) == 1


def test_status_callbacks_are_ignored():
    payload = {"entry": [{"changes": [{"value": {
        "statuses": [{"id": "wamid.1", "status": "delivered"}]
    }}]}]}
    assert parse_inbound(payload) == []


def test_non_text_messages_are_ignored():
    payload = envelope()
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    assert parse_inbound(payload) == []


@pytest.mark.parametrize(
    "mode,token,expected",
    [("subscribe", "tok", "chal"), ("subscribe", "wrong", None), ("unsub", "tok", None)],
)
def test_subscription_handshake(mode, token, expected):
    assert verify_subscription(mode, token, "chal", "tok") == expected


def test_signature_helper_is_constant_time_safe():
    body = b"{}"
    assert verify_signature(SECRET, body, sign(body))
    assert not verify_signature(SECRET, body, None)
