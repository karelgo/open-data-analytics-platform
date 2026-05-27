"""Wajong-aanvragen stub. SYNTHETIC — NOT FOR REAL USE.

UC-02 hoog-risico AI is in deze referentie placeholder; deze generator levert
*minimaal* veld-niveau data, geen medische bijzondere PG.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from ._common import envelope, make_rng


@dataclass
class WajongDossier:
    case_id: str
    bsn: str
    regime: str  # 'oude_Wajong' | 'Wajong_2010' | 'Wajong_2015'
    arbeidsvermogen: str  # 'volledig' | 'gedeeltelijk' | 'duurzaam_geen'
    ingangsdatum: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_eligibility_case(rng: random.Random, bsn: str) -> WajongDossier:
    return WajongDossier(
        case_id=f"WAJ-{rng.randint(10**8, 10**9 - 1)}",
        bsn=bsn,
        regime=rng.choices(["oude_Wajong", "Wajong_2010", "Wajong_2015"], weights=[20, 50, 30])[0],
        arbeidsvermogen=rng.choices(
            ["volledig", "gedeeltelijk", "duurzaam_geen"], weights=[40, 40, 20]
        )[0],
        ingangsdatum=f"20{rng.randint(15, 24)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
    )


def generate_eligibility_cases(
    persona_bsns: list[str], rate: float = 0.05, seed: int | None = None
) -> Iterator[WajongDossier]:
    rng = make_rng(seed)
    for bsn in persona_bsns:
        if rng.random() < rate:
            yield generate_eligibility_case(rng, bsn)


def to_kafka_envelope(d: WajongDossier) -> dict[str, Any]:
    return envelope(d.to_dict(), event_type="wajong.dossier.geopend")
