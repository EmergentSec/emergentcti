import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.note import ObservableNote


async def create_note(
    db: AsyncSession,
    observable_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
) -> ObservableNote:
    note = ObservableNote(
        observable_id=observable_id,
        user_id=user_id,
        content=content,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note, ["user"])
    return note


async def list_notes(
    db: AsyncSession, observable_id: uuid.UUID
) -> list[ObservableNote]:
    result = await db.execute(
        select(ObservableNote)
        .where(ObservableNote.observable_id == observable_id)
        .order_by(ObservableNote.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_note(
    db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(ObservableNote).where(ObservableNote.id == note_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        return False
    if note.user_id != user_id:
        return False
    await db.delete(note)
    await db.flush()
    return True
