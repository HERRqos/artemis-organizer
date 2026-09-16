"""Per-sender conversation state in Redis.

Only the message history and an escalation flag live here. Anything
that must survive (appointments) lives in Google Calendar, not Redis.
"""
import json

import redis


class SessionStore:
    def __init__(self, url: str, ttl_seconds: int = 12 * 3600, max_turns: int = 20):
        self._r = redis.Redis.from_url(url, decode_responses=True, socket_keepalive=True)
        self._ttl = ttl_seconds
        self._max_turns = max_turns

    def _key(self, sender: str) -> str:
        return f"session:{sender}"

    def history(self, sender: str) -> list[dict]:
        raw = self._r.get(self._key(sender))
        return json.loads(raw) if raw else []

    def save(self, sender: str, messages: list[dict]) -> None:
        trimmed = messages[-self._max_turns * 2 :]
        self._r.set(self._key(sender), json.dumps(trimmed), ex=self._ttl)

    def escalate(self, sender: str, hours: int = 24) -> None:
        """Mute the bot for this sender so she can take over by hand."""
        self._r.set(f"handoff:{sender}", "1", ex=hours * 3600)

    def is_escalated(self, sender: str) -> bool:
        return bool(self._r.exists(f"handoff:{sender}"))
