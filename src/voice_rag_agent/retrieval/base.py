"""The retriever contract shared by the local index and the AWS-backed one."""

from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class Hit:
    section_id: str  # "<page path>#<anchor>", identical across languages
    page: str  # e.g. "tutorial/security/oauth2-jwt.md"
    lang: str  # "en" or "es"
    title: str  # page title
    heading: str  # heading of the section the chunk came from
    url: str  # public FastAPI docs URL with anchor
    text: str
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


class Retriever(Protocol):
    name: str

    def search(self, query: str, lang: str | None = None, k: int = 5) -> list[Hit]:
        """Return up to k hits, at most one per section_id, best first.

        lang is a preference, not a filter: hits in that language rank first
        when two chunks share a section.
        """
        ...
