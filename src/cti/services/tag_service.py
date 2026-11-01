"""Flat tags (#15): normalization, persistence, and assignment."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from cti.models.export_profile import ExportProfile
from cti.models.tag import (
    TAG_NAME_MAX_LENGTH,
    Tag,
    export_profile_tags,
    observable_tags,
    report_tags,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable, Sequence

    from sqlalchemy import Table
    from sqlalchemy.ext.asyncio import AsyncSession

_WHITESPACE_RUN = re.compile(r"\s+")
_ALLOWED = re.compile(r"[a-z0-9._:/-]+")
MAX_TAGS_PER_ITEM = 100


class TagValidationError(ValueError):
    """A tag name is invalid after normalization."""


class TagInUseError(Exception):
    """An export profile filters on the tag, so it cannot be deleted."""

    def __init__(self, profile_names: list[str]) -> None:
        super().__init__(
            "Tag is referenced by export profiles: " + (", ".join(profile_names) or "unknown")
        )
        self.profile_names = profile_names


class TagNotFoundError(Exception):
    """A referenced tag name does not exist."""

    def __init__(self, names: list[str]) -> None:
        super().__init__("Tag not found: " + ", ".join(names))
        self.names = names


def normalize_tag(raw: str) -> str:
    """Trim, collapse whitespace runs to ``-``, casefold; then validate.

    Raises:
        TagValidationError: with a message suitable for the API caller.
    """
    name = _WHITESPACE_RUN.sub("-", raw.strip()).casefold()
    if not name:
        raise TagValidationError("Tag name is required")
    if len(name) > TAG_NAME_MAX_LENGTH:
        raise TagValidationError(
            f"Tag name must be at most {TAG_NAME_MAX_LENGTH} characters after normalization"
        )
    if not _ALLOWED.fullmatch(name):
        raise TagValidationError(
            f"Tag {name!r} may only contain a-z, 0-9 and the characters . _ : / -"
        )
    return name


def normalize_tags(raw_names: Iterable[str]) -> list[str]:
    """Normalize and deduplicate, preserving first-seen order."""
    names = list(dict.fromkeys(normalize_tag(n) for n in raw_names))
    if len(names) > MAX_TAGS_PER_ITEM:
        raise TagValidationError(f"At most {MAX_TAGS_PER_ITEM} tags per item")
    return names


async def list_tags(db: AsyncSession, prefix: str | None = None) -> list[tuple[Tag, int, int]]:
    """Tags sorted by name with observable and report usage counts."""
    obs_count = (
        select(func.count())
        .select_from(observable_tags)
        .where(observable_tags.c.tag_id == Tag.id)
        .correlate(Tag)
        .scalar_subquery()
    )
    report_count = (
        select(func.count())
        .select_from(report_tags)
        .where(report_tags.c.tag_id == Tag.id)
        .correlate(Tag)
        .scalar_subquery()
    )
    stmt = select(Tag, obs_count, report_count).order_by(Tag.name)
    if prefix:
        # Normalize the prefix the same way as names, without validating it.
        needle = _WHITESPACE_RUN.sub("-", prefix.strip()).casefold()
        escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Tag.name.like(f"{escaped}%", escape="\\"))
    rows = await db.execute(stmt)
    return [(tag, int(o or 0), int(r or 0)) for tag, o, r in rows.all()]


async def get_tag(db: AsyncSession, tag_id: uuid.UUID) -> Tag | None:
    return await db.get(Tag, tag_id)


async def get_or_create_tag(db: AsyncSession, name: str) -> tuple[Tag, bool]:
    """Return ``(tag, created)`` for an already-normalized name."""
    existing = await db.scalar(select(Tag).where(Tag.name == name))
    if existing is not None:
        return existing, False
    tag = Tag(name=name)
    try:
        async with db.begin_nested():
            db.add(tag)
            await db.flush()
    except IntegrityError:
        # Lost a race with a concurrent create of the same name.
        existing = await db.scalar(select(Tag).where(Tag.name == name))
        if existing is None:
            raise
        return existing, False
    return tag, True


async def _tags_by_name(db: AsyncSession, names: Sequence[str], *, create: bool) -> list[Tag]:
    tags: list[Tag] = []
    missing: list[str] = []
    for name in names:
        if create:
            tag, _ = await get_or_create_tag(db, name)
            tags.append(tag)
            continue
        tag = await db.scalar(select(Tag).where(Tag.name == name))
        if tag is None:
            missing.append(name)
        else:
            tags.append(tag)
    if missing:
        raise TagNotFoundError(missing)
    return tags


async def _replace_assignments(
    db: AsyncSession, table: Table, owner_column: str, owner_id: uuid.UUID, tags: Sequence[Tag]
) -> None:
    owner = table.c[owner_column]
    await db.execute(delete(table).where(owner == owner_id))
    if tags:
        await db.execute(
            insert(table), [{owner_column: owner_id, "tag_id": tag.id} for tag in tags]
        )
    await db.flush()


async def set_observable_tags(
    db: AsyncSession, observable_id: uuid.UUID, raw_names: Iterable[str]
) -> None:
    """Replace an observable's tag set; unknown names are created."""
    tags = await _tags_by_name(db, normalize_tags(raw_names), create=True)
    await _replace_assignments(db, observable_tags, "observable_id", observable_id, tags)


async def set_report_tags(db: AsyncSession, report_id: uuid.UUID, raw_names: Iterable[str]) -> None:
    """Replace a report's tag set; unknown names are created."""
    tags = await _tags_by_name(db, normalize_tags(raw_names), create=True)
    await _replace_assignments(db, report_tags, "report_id", report_id, tags)


async def resolve_profile_tags(db: AsyncSession, raw_names: Iterable[str]) -> list[Tag]:
    """Existing tags for a profile filter.

    Raises:
        TagValidationError: a name is invalid.
        TagNotFoundError: a name does not exist (profiles never create tags).
    """
    return await _tags_by_name(db, normalize_tags(raw_names), create=False)


async def _referencing_profile_names(db: AsyncSession, tag_id: uuid.UUID) -> list[str]:
    rows = await db.execute(
        select(ExportProfile.name)
        .join(export_profile_tags, export_profile_tags.c.export_profile_id == ExportProfile.id)
        .where(export_profile_tags.c.tag_id == tag_id)
        .order_by(ExportProfile.name)
    )
    return [row[0] for row in rows.all()]


async def delete_tag(db: AsyncSession, tag: Tag) -> None:
    """Delete a tag and all its assignments.

    Raises:
        TagInUseError: an export profile filters on it (fail closed).
    """
    names = await _referencing_profile_names(db, tag.id)
    if names:
        raise TagInUseError(names)
    tag_id = tag.id
    # Explicit deletes as well as ON DELETE CASCADE, so SQLite (FKs off) agrees.
    await db.execute(delete(observable_tags).where(observable_tags.c.tag_id == tag_id))
    await db.execute(delete(report_tags).where(report_tags.c.tag_id == tag_id))
    await db.delete(tag)
    try:
        await db.flush()
    except IntegrityError:
        # A profile started referencing the tag after the check; RESTRICT refused.
        await db.rollback()
        raise TagInUseError(await _referencing_profile_names(db, tag_id)) from None


def tag_filter_names(raw_names: Iterable[str] | None) -> list[str]:
    """Normalize a repeatable ``tag`` query parameter (empty = no tag filter)."""
    if not raw_names:
        return []
    return list(dict.fromkeys(normalize_tag(n) for n in raw_names))
