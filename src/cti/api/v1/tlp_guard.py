"""Route helpers for "TLP:RED never leaves through an API-key path" (#15).

The rule itself lives in :mod:`cti.services.tlp`; these helpers only turn it
into consistent 404 responses, so a RED item is indistinguishable from a
missing one for API-key callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from cti.services.tlp import hide_red_for, is_red_observable, is_red_report

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_observable_visible(
    db: AsyncSession,
    auth: object,
    observable_id: uuid.UUID,
    detail: str = "Observable not found",
) -> None:
    if hide_red_for(auth) and await is_red_observable(db, observable_id):
        raise HTTPException(status_code=404, detail=detail)


async def ensure_report_visible(
    db: AsyncSession,
    auth: object,
    report_id: uuid.UUID,
    detail: str = "Report not found",
) -> None:
    if hide_red_for(auth) and await is_red_report(db, report_id):
        raise HTTPException(status_code=404, detail=detail)
