"""FIRST TLP 2.0 markings (#15).

Markings are stored as these exact strings in nullable ``varchar(16)``
columns; SQL ``NULL`` means *Unspecified*, which is not a rank and is never
treated as CLEAR. The sharing rules live in :mod:`cti.services.tlp`.
"""

from __future__ import annotations

import enum


class Tlp(enum.StrEnum):
    CLEAR = "clear"
    GREEN = "green"
    AMBER = "amber"
    AMBER_STRICT = "amber+strict"
    RED = "red"


TLP_RANK: dict[Tlp, int] = {
    Tlp.CLEAR: 0,
    Tlp.GREEN: 1,
    Tlp.AMBER: 2,
    Tlp.AMBER_STRICT: 3,
    Tlp.RED: 4,
}

TLP_VALUES: tuple[str, ...] = tuple(t.value for t in Tlp)

# Token used for Unspecified in query parameters and per-marking counters.
UNSPECIFIED = "unspecified"

TLP_COLUMN_LENGTH = 16


def tlp_check_sql(column: str) -> str:
    """CHECK constraint body: the column is NULL or one of the five values."""
    allowed = ", ".join(f"'{v}'" for v in TLP_VALUES)
    return f"{column} IS NULL OR {column} IN ({allowed})"
