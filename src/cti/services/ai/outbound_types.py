"""Types shared by the outbound-content guard and the AI gateway (#17).

An ``ApprovedOutbound`` can only be produced by ``outbound.approve``, after the
server has rebuilt the exact content, re-checked TLP and verified the digest
the user saw in the preview. The gateway refuses content-bearing actions
without one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cti.models.ai import AiProvider

OutboundItemType = Literal["report", "observable"]


@dataclass(frozen=True, slots=True)
class OutboundRef:
    type: OutboundItemType
    id: str


@dataclass(frozen=True, slots=True)
class ApprovedOutbound:
    provider: AiProvider
    model: str
    digest: str
    content: str
    item_refs: tuple[OutboundRef, ...]
