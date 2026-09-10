"""Practice FAQ lookup.

MVP: a small YAML/JSON file of her own answers, matched crudely. The
signature is already the one a pgvector-backed retriever will have, so
phase 2 swaps the body and nothing above it changes.
"""
import json
import os
import re
from dataclasses import dataclass

FAQ_PATH = os.environ.get("FAQ_PATH", "/srv/data/practice.json")


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer: str


class PracticeInfo:
    def __init__(self, path: str = FAQ_PATH):
        with open(path, encoding="utf-8") as fh:
            self._entries = [FaqEntry(**e) for e in json.load(fh)]

    def search(self, query: str, k: int = 2) -> list[FaqEntry]:
        terms = set(re.findall(r"\w+", query.lower()))
        scored = [
            (len(terms & set(re.findall(r"\w+", (e.question + " " + e.answer).lower()))), e)
            for e in self._entries
        ]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [e for score, e in scored[:k] if score > 0]
