"""Small data model shared by the site adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Page:
    """A fully rendered output page."""

    path: str
    html: str
    title: str
    description: str = ""
    kind: str = "page"


@dataclass
class BuildStats:
    instructions: int = 0
    registers: int = 0
    listings: int = 0
    assets: int = 0
