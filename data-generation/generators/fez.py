"""FEZ-aggregaten stub. SYNTHETIC — NOT FOR REAL USE.

Geaggregeerde claim_cost per wet x maand x regio. Geen PII.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from ._common import envelope, make_rng


@dataclass
class UitkeringslastAggregaat:
    jaar: int
    maand: int
    wet: str  # 'WW' | 'WIA' | 'Wajong' | 'ZW' | 'TW' | 'WAO'
    regio_code: str
    uitbetaald_bruto_eur: int
    aantal_uitkeringen: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_WETTEN = ["WW", "WIA", "Wajong", "ZW", "TW", "WAO"]
_REGIOS = ["AMS", "RTM", "DHN", "UTR", "EHV", "GRO", "ZWO", "ARN", "BRD"]


def generate_fez_aggregaten(seed: int | None = None) -> Iterator[UitkeringslastAggregaat]:
    """Maandelijkse aggregaten 2023-2025 per wet x regio."""
    rng = make_rng(seed)
    for jaar in (2023, 2024, 2025):
        for maand in range(1, 13):
            for wet in _WETTEN:
                for regio in _REGIOS:
                    base = {
                        "WW": 12_000_000,
                        "WIA": 28_000_000,
                        "Wajong": 8_000_000,
                        "ZW": 4_000_000,
                        "TW": 1_500_000,
                        "WAO": 22_000_000,
                    }[wet]
                    yield UitkeringslastAggregaat(
                        jaar=jaar,
                        maand=maand,
                        wet=wet,
                        regio_code=regio,
                        uitbetaald_bruto_eur=int(base * rng.uniform(0.7, 1.3) / len(_REGIOS)),
                        aantal_uitkeringen=rng.randint(500, 5000),
                    )


def to_kafka_envelope(a: UitkeringslastAggregaat) -> dict[str, Any]:
    return envelope(a.to_dict(), event_type="fez.claim_cost.maand")
