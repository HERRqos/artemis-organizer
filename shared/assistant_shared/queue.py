"""Queue abstraction.

Redis Streams today; SQS later is a new class implementing the same
Protocol plus a config change. Consumer groups give at-least-once
delivery with an explicit ack, which is the semantic SQS also gives.
"""
import json
from dataclasses import dataclass
from typing import Any, Protocol

import redis


@dataclass(frozen=True)
class QueuedMessage:
    receipt: str          # stream id / SQS receipt handle
    payload: dict[str, Any]


class Queue(Protocol):
    def publish(self, payload: dict[str, Any]) -> str: ...
    def consume(self, consumer: str, count: int = 1, block_ms: int = 5000) -> list[QueuedMessage]: ...
    def ack(self, receipt: str) -> None: ...


class RedisStreamQueue:
    def __init__(self, url: str, stream: str, group: str = "workers"):
        self._r = redis.Redis.from_url(url, decode_responses=True)
        self._stream = stream
        self._group = group
        self._ensure_group()

    def _ensure_group(self) -> None:
        try:
            self._r.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, payload: dict[str, Any]) -> str:
        return self._r.xadd(self._stream, {"body": json.dumps(payload)})

    def consume(self, consumer: str, count: int = 1, block_ms: int = 5000) -> list[QueuedMessage]:
        resp = self._r.xreadgroup(
            self._group, consumer, {self._stream: ">"}, count=count, block=block_ms
        )
        if not resp:
            return []
        _, entries = resp[0]
        return [QueuedMessage(receipt=mid, payload=json.loads(f["body"])) for mid, f in entries]

    def ack(self, receipt: str) -> None:
        self._r.xack(self._stream, self._group, receipt)
