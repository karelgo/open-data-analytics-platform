"""WIA-request stub. SYNTHETIC DATA — NOT FOR REAL USE."""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from ._common import envelope, make_rng


@dataclass
class WIAAanvraag:
    application_id: str
    bsn: str
    aanvraag_datum: str
    eerste_ziektedag: str
    onderdeel: str  # 'WGA' | 'IVA'
    regio_code: str  # NL-regio (synthetisch)
    status: str  # 'INGEDIEND' | 'IN_BEHANDELING' | 'TOEGEKEND_WGA' | 'TOEGEKEND_IVA' | 'AFGEWEZEN'
    arbeidsongeschikt_pct: int  # 0..100

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REGIOS = ["AMS", "RTM", "DHN", "UTR", "EHV", "GRO", "ZWO", "ARN", "BRD"]


def generate_claim_application(rng: random.Random, bsn: str) -> WIAAanvraag:
    pct = rng.choices([0, 35, 45, 60, 80, 100], weights=[5, 15, 20, 25, 20, 15])[0]
    onderdeel = "IVA" if pct >= 80 else "WGA"
    return WIAAanvraag(
        application_id=f"WIA-{rng.randint(10**8, 10**9 - 1)}",
        bsn=bsn,
        aanvraag_datum=f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        eerste_ziektedag=f"2023-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        onderdeel=onderdeel,
        regio_code=rng.choice(_REGIOS),
        status=rng.choices(
            ["INGEDIEND", "IN_BEHANDELING", "TOEGEKEND_WGA", "TOEGEKEND_IVA", "AFGEWEZEN"],
            weights=[5, 30, 35, 15, 15],
        )[0],
        arbeidsongeschikt_pct=pct,
    )


def generate_wia_request(
    persona_bsns: list[str], rate: float = 0.15, seed: int | None = None
) -> Iterator[WIAAanvraag]:
    rng = make_rng(seed)
    for bsn in persona_bsns:
        if rng.random() < rate:
            yield generate_claim_application(rng, bsn)


def to_kafka_envelope(a: WIAAanvraag) -> dict[str, Any]:
    return envelope(a.to_dict(), event_type="wia.aanvraag.ingediend")
