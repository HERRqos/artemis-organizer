"""Pre-LLM safety gate.

Anything that looks like crisis or clinical content must not reach the
model at all — it goes straight to a human handoff. This list is a
placeholder: review and extend it WITH your friend, and keep the bot's
reply free of anything that reads as clinical advice.
"""
import re
import unicodedata

CRISIS_PATTERNS = [
    r"\bsuicid",
    r"\bmatarme\b",
    r"\bquitarme la vida\b",
    r"\bno quiero vivir\b",
    r"\bhacerme dan[oñ]",
    r"\bautolesi",
    r"\bemergencia\b",
    r"\bcrisis\b",
]

_COMPILED = [re.compile(p) for p in CRISIS_PATTERNS]


def _normalize(text: str) -> str:
    lowered = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )


def needs_immediate_handoff(text: str) -> bool:
    normalized = _normalize(text)
    return any(p.search(normalized) for p in _COMPILED)
