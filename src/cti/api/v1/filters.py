"""Shared query-parameter parsing for tag and TLP filters (#15)."""

from __future__ import annotations

from fastapi import HTTPException

from cti.models.tlp import UNSPECIFIED, Tlp
from cti.services import tag_service

_TLP_TOKENS = frozenset({UNSPECIFIED, *(t.value for t in Tlp)})


def parse_tlp_tokens(raw: list[str] | None) -> list[str]:
    """Validate a repeatable ``tlp`` query parameter (a marking or ``unspecified``)."""
    tokens = [t.strip().lower() for t in raw or []]
    if any(t not in _TLP_TOKENS for t in tokens):
        raise HTTPException(
            status_code=422,
            detail=f"tlp must be one of: {', '.join(sorted(_TLP_TOKENS))}",
        )
    return list(dict.fromkeys(tokens))


def parse_tag_names(raw: list[str] | None) -> list[str]:
    """Normalize a repeatable ``tag`` query parameter (empty = no tag filter)."""
    try:
        return tag_service.tag_filter_names(raw)
    except tag_service.TagValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
