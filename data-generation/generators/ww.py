"""WW-request stub.

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
Production-volwaardige generator: fase 5.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from ._common import envelope, make_rng


@dataclass
class WWAanvraag:
    application_id: str
    bsn: str
    aanvraag_datum: str
    laatste_werkdag: str
    reden_einde_dienstverband: (
        str  # 'ontslag_werkgever' | 'einde_contract' | 'wederzijds_goedvinden' | 'eigen_initiatief'
    )
    status: str  # 'INGEDIEND' | 'TOEGEKEND' | 'AFGEWEZEN' | 'IN_BEHANDELING'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_service_request_application(rng: random.Random, bsn: str) -> WWAanvraag:
    return WWAanvraag(
        application_id=f"WW-{rng.randint(10**8, 10**9 - 1)}",
        bsn=bsn,
        aanvraag_datum=f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        laatste_werkdag=f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        reden_einde_dienstverband=rng.choice(
            ["ontslag_werkgever", "einde_contract", "wederzijds_goedvinden", "eigen_initiatief"]
        ),
        status=rng.choices(
            ["INGEDIEND", "IN_BEHANDELING", "TOEGEKEND", "AFGEWEZEN"],
            weights=[10, 30, 50, 10],
        )[0],
    )


def generate_ww_request(
    persona_bsns: list[str], rate: float = 0.3, seed: int | None = None
) -> Iterator[WWAanvraag]:
    """Genereer WW-request for a fractie van de personen."""
    rng = make_rng(seed)
    for bsn in persona_bsns:
        if rng.random() < rate:
            yield generate_service_request_application(rng, bsn)


def to_kafka_envelope(a: WWAanvraag) -> dict[str, Any]:
    return envelope(a.to_dict(), event_type="ww.aanvraag.ingediend")
