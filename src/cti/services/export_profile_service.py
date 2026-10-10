"""Saved export profiles: shared filter configuration for repeatable exports."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.export_profile import ExportFormat, ExportProfile
from cti.models.feed import Feed
from cti.services import observable_service

PREVIEW_SAMPLE_SIZE = 20


class DuplicateProfileNameError(Exception):
    """Another profile already uses this name."""


class ProfileFeedNotFoundError(Exception):
    """The profile references a feed that does not exist."""


async def list_profiles(db: AsyncSession) -> list[ExportProfile]:
    result = await db.execute(select(ExportProfile).order_by(ExportProfile.name))
    return list(result.scalars().all())


async def get_profile(db: AsyncSession, profile_id: uuid.UUID) -> ExportProfile | None:
    return await db.get(ExportProfile, profile_id)


async def list_profiles_for_feed(db: AsyncSession, feed_id: uuid.UUID) -> list[ExportProfile]:
    """Profiles whose saved filters reference the given feed."""
    result = await db.execute(
        select(ExportProfile)
        .where(ExportProfile.feed_id == feed_id)
        .order_by(ExportProfile.name)
    )
    return list(result.scalars().all())


async def _ensure_name_available(
    db: AsyncSession, name: str, exclude_id: uuid.UUID | None = None
) -> None:
    stmt = select(ExportProfile.id).where(ExportProfile.name == name)
    if exclude_id is not None:
        stmt = stmt.where(ExportProfile.id != exclude_id)
    if (await db.execute(stmt)).first() is not None:
        raise DuplicateProfileNameError


async def _ensure_feed_exists(db: AsyncSession, feed_id: uuid.UUID | None) -> None:
    if feed_id is not None and await db.get(Feed, feed_id) is None:
        raise ProfileFeedNotFoundError


def is_foreign_key_violation(exc: IntegrityError) -> bool:
    """Whether an IntegrityError is a foreign-key violation (vs. unique/check)."""
    orig = exc.orig
    # PostgreSQL SQLSTATE 23503 = foreign_key_violation.
    if getattr(orig, "sqlstate", None) == "23503":
        return True
    return "foreign key" in str(orig).lower()


async def _flush(db: AsyncSession) -> None:
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if is_foreign_key_violation(exc):
            # The feed was deleted between our existence check and the write.
            raise ProfileFeedNotFoundError from None
        # Lost a race on the unique name.
        raise DuplicateProfileNameError from None


async def create_profile(db: AsyncSession, data: dict) -> ExportProfile:
    await _ensure_name_available(db, data["name"])
    await _ensure_feed_exists(db, data.get("feed_id"))
    profile = ExportProfile(**data)
    db.add(profile)
    await _flush(db)
    await db.refresh(profile)
    return profile


async def update_profile(db: AsyncSession, profile: ExportProfile, data: dict) -> ExportProfile:
    """Apply the provided fields; explicit ``None`` clears a nullable filter."""
    if "name" in data and data["name"] != profile.name:
        await _ensure_name_available(db, data["name"], exclude_id=profile.id)
    if data.get("feed_id") is not None and data["feed_id"] != profile.feed_id:
        await _ensure_feed_exists(db, data["feed_id"])
    for key, value in data.items():
        setattr(profile, key, value)
    await _flush(db)
    await db.refresh(profile)
    return profile


async def delete_profile(db: AsyncSession, profile: ExportProfile) -> None:
    await db.delete(profile)
    await db.flush()


async def get_profile_values(db: AsyncSession, profile: ExportProfile) -> tuple[list[str], int]:
    """Evaluate a profile against current data and the current allowlist.

    Returns ``(values, excluded_allowlisted)``. Text profiles yield the
    complete blocklist (alphabetical, deduplicated, never truncated); JSON
    profiles yield values in export order (newest first). Text values are
    line-safe; JSON values are literal.
    """
    is_text = profile.format is ExportFormat.TEXT
    return await observable_service.get_export_values(
        db,
        obs_type=profile.type,
        confidence_min=profile.confidence_min,
        max_age_days=profile.max_age_days,
        feed_id=profile.feed_id,
        order="value" if is_text else "recent",
        line_safe=is_text,
    )
