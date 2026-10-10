from __future__ import annotations

import enum

from sqlalchemy import CheckConstraint, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin, UUIDMixin
from cti.models.observable import ObservableType


class AllowlistKind(str, enum.Enum):
    EXACT = "exact"
    CIDR = "cidr"
    DOMAIN_SUFFIX = "domain_suffix"


class AllowlistEntry(UUIDMixin, TimestampMixin, Base):
    """A reversible export-suppression policy.

    Matching happens at read/export time against the canonical ``value``;
    nothing is written to observables, so removing an entry restores them.
    """

    __tablename__ = "allowlist_entries"
    __table_args__ = (
        UniqueConstraint("kind", "observable_type", "value", name="uq_allowlist_entry_policy"),
        CheckConstraint(
            "kind IN ('exact', 'cidr', 'domain_suffix')", name="ck_allowlist_entry_kind"
        ),
    )

    kind: Mapped[AllowlistKind] = mapped_column(
        Enum(
            AllowlistKind,
            values_callable=lambda x: [e.value for e in x],
            native_enum=False,
            length=32,
        ),
    )
    value: Mapped[str] = mapped_column(String(2048))
    observable_type: Mapped[ObservableType] = mapped_column(
        Enum(ObservableType, values_callable=lambda x: [e.value for e in x]),
    )
    reason: Mapped[str] = mapped_column(String(500))

    def __repr__(self) -> str:
        return (
            f"<AllowlistEntry(kind={self.kind!r}, type={self.observable_type!r}, "
            f"value={self.value!r})>"
        )
