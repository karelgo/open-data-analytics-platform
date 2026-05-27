"""CRM customer interaction stub. SYNTHETIC — NOT FOR REAL USE."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from ._common import envelope, make_rng


@dataclass
class KlantContact:
    contact_id: str
    bsn: str
    kanaal: str  # 'telefoon' | 'balie' | 'beeldbellen' | 'workspace_bericht' | 'mail'
    onderwerp: str  # 'WW' | 'WIA' | 'Wajong' | 'algemeen'
    timestamp: str
    duur_seconden: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_customer interactionen(
    persona_bsns: list[str], avg_per_persoon: float = 0.5, seed: int | None = None
) -> Iterator[KlantContact]:
    rng = make_rng(seed)
    kanalen = ["telefoon", "balie", "beeldbellen", "workspace_bericht", "mail"]
    onderwerpen = ["WW", "WIA", "Wajong", "algemeen"]
    for bsn in persona_bsns:
        n = rng.choices([0, 1, 2, 3], weights=[40, 35, 20, 5])[0]
        for _ in range(n):
            kanaal = rng.choice(kanalen)
            duur = rng.randint(60, 1800) if kanaal in ("telefoon", "beeldbellen", "balie") else None
            yield KlantContact(
                contact_id=f"CC-{rng.randint(10**9, 10**10 - 1)}",
                bsn=bsn,
                kanaal=kanaal,
                onderwerp=rng.choice(onderwerpen),
                timestamp=f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T"
                f"{rng.randint(8, 17):02d}:{rng.randint(0, 59):02d}:00Z",
                duur_seconden=duur,
            )


def to_kafka_envelope(c: KlantContact) -> dict[str, Any]:
    return envelope(c.to_dict(), event_type="crm.contact.gelogd")
