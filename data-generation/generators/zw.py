"""Ziektewet-meldingen stub. SYNTHETIC — NOT FOR REAL USE."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from ._common import envelope, make_rng


@dataclass
class ZWMelding:
    incident_id: str
    bsn: str
    eerste_ziektedag: str
    duur_dagen: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_incident_reporten(
    persona_bsns: list[str], rate: float = 0.2, seed: int | None = None
) -> Iterator[ZWMelding]:
    rng = make_rng(seed)
    for bsn in persona_bsns:
        if rng.random() < rate:
            yield ZWMelding(
                incident_id=f"ZW-{rng.randint(10**8, 10**9 - 1)}",
                bsn=bsn,
                eerste_ziektedag=f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                duur_dagen=rng.randint(1, 730),
            )


def to_kafka_envelope(m: ZWMelding) -> dict[str, Any]:
    return envelope(m.to_dict(), event_type="zw.melding.gemeld")
