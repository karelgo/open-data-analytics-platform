"""Polisadministratie-stub — IKV's, dienstverbanden, lonen.

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.

Productie-volwaardige generator komt in fase 5 zodra dbt staging-models
de structuur eisen (UC-07 datakwaliteit als anchor).
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from ._common import envelope, make_faker, make_rng


@dataclass
class IKV:
    """Inkomstenverhouding — kerneenheid polisadministratie."""

    ikv_id: str  # UUID-achtig, opaque
    bsn: str  # FK naar persona
    lh_nummer: str  # Loonheffingennummer werkgever (synthetisch)
    werkgever_naam: str
    aanvang_dienstverband: str  # ISO-date
    einde_dienstverband: str | None  # null = lopend
    loon_bruto_jaar: int  # in euro

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _generate_lh_nummer(rng: random.Random) -> str:
    """Synthetisch loonheffingennummer: 9 cijfers + 'L' + 2 cijfers (bv. '123456789L01')."""
    return "".join(str(rng.randint(0, 9)) for _ in range(9)) + "L" + f"{rng.randint(1, 99):02d}"


def generate_ikv(rng: random.Random, fake, bsn: str) -> IKV:
    """Eén IKV voor een gegeven persoon."""
    aanvang_jaar = rng.randint(2018, 2025)
    einde_optie = rng.random()
    if einde_optie < 0.7:
        einde = None
    else:
        einde_jaar = aanvang_jaar + rng.randint(1, 5)
        einde = f"{einde_jaar}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"

    # Salaris: log-normal-achtig, range 18k-120k
    loon = int(rng.lognormvariate(mu=10.6, sigma=0.4))
    loon = max(18000, min(loon, 120000))

    return IKV(
        ikv_id=f"IKV-{rng.randint(10**9, 10**10 - 1)}",
        bsn=bsn,
        lh_nummer=_generate_lh_nummer(rng),
        werkgever_naam=fake.company(),
        aanvang_dienstverband=f"{aanvang_jaar}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        einde_dienstverband=einde,
        loon_bruto_jaar=loon,
    )


def generate_ikvs_for_persona(rng: random.Random, fake, bsn: str, max_ikvs: int = 3) -> list[IKV]:
    """1..max_ikvs IKV's per persoon. Realiteit: ~1.5 gemiddeld."""
    n = rng.choices([1, 2, 3], weights=[60, 30, 10])[0]
    n = min(n, max_ikvs)
    return [generate_ikv(rng, fake, bsn) for _ in range(n)]


def generate_ikvs(persona_bsns: list[str], seed: int | None = None) -> Iterator[IKV]:
    rng = make_rng(seed)
    fake = make_faker(seed=seed)
    for bsn in persona_bsns:
        yield from generate_ikvs_for_persona(rng, fake, bsn)


def to_kafka_envelope(ikv: IKV) -> dict[str, Any]:
    return envelope(ikv.to_dict(), event_type="polisadm.ikv.aangelegd")
