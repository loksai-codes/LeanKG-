"""Domain pack models. TODO: full implementation in M1."""

from __future__ import annotations

from pydantic import BaseModel


class DomainPack(BaseModel):
    name: str
