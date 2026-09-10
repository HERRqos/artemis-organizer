from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class InboundMessage:
    """Channel-neutral inbound message. Instagram maps onto the same shape."""
    message_id: str
    channel: str          # "whatsapp" | "instagram"
    sender: str           # wa_id / IG scoped id
    text: str
    timestamp: int
    profile_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "InboundMessage":
        return InboundMessage(**d)
