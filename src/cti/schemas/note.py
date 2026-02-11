import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class NoteAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    observable_id: uuid.UUID
    content: str
    author: NoteAuthor
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_note(cls, note: Any) -> "NoteResponse":
        return cls(
            id=note.id,
            observable_id=note.observable_id,
            content=note.content,
            author=NoteAuthor(id=note.user.id, username=note.user.username),
            created_at=note.created_at,
            updated_at=note.updated_at,
        )
