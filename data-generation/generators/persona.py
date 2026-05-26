"""Persoon-generator met geldige test-BSN's (11-proef, 9-prefix).

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.

Test-BSN's beginnen met '9'. BRP geeft die niet uit aan natuurlijke personen.
Elke BSN doorstaat de 11-proef (zie `is_valid_bsn`).
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from ._common import envelope, make_faker, make_rng

# 11-proef-gewichten voor BSN. BSN ABCDEFGHI:
#   (9*A + 8*B + 7*C + 6*D + 5*E + 4*F + 3*G + 2*H - 1*I) mod 11 == 0
BSN_WEIGHTS_8: tuple[int, ...] = (9, 8, 7, 6, 5, 4, 3, 2)
BSN_WEIGHTS_9: tuple[int, ...] = (9, 8, 7, 6, 5, 4, 3, 2, -1)

# Test-BSN-prefix; BSN's beginnend met 9 worden niet door BRP uitgegeven.
TEST_BSN_PREFIX = "9"


def calculate_bsn_check_digit(first_8_digits: str) -> int | None:
    """Bereken het 9e cijfer voor een gegeven prefix van 8 cijfers.

    Retourneer None als er geen geldig 9e cijfer is (mod 11 == 10).
    """
    if len(first_8_digits) != 8 or not first_8_digits.isdigit():
        raise ValueError(f"first_8_digits moet 8 cijfers zijn, kreeg: {first_8_digits!r}")
    digits = [int(c) for c in first_8_digits]
    total = sum(w * d for w, d in zip(BSN_WEIGHTS_8, digits, strict=True))
    check = total % 11
    return None if check == 10 else check


def is_valid_bsn(bsn: str) -> bool:
    """Verifieer dat een BSN aan de 11-proef voldoet.

    Eisen:
      - 9 cijfers
      - eerste cijfer != '0' (BSN-conventie)
      - (9*A + 8*B + 7*C + 6*D + 5*E + 4*F + 3*G + 2*H - 1*I) mod 11 == 0
    """
    if not isinstance(bsn, str) or len(bsn) != 9 or not bsn.isdigit():
        return False
    if bsn[0] == "0":
        return False
    digits = [int(c) for c in bsn]
    total = sum(w * d for w, d in zip(BSN_WEIGHTS_9, digits, strict=True))
    return total % 11 == 0


def generate_test_bsn(rng: random.Random) -> str:
    """Genereer een geldig test-BSN startend met 9.

    Probeert net zo lang tot er een prefix is met geldig 9e cijfer.
    """
    for _ in range(100):
        first_8 = TEST_BSN_PREFIX + "".join(str(rng.randint(0, 9)) for _ in range(7))
        check = calculate_bsn_check_digit(first_8)
        if check is not None:
            bsn = first_8 + str(check)
            assert is_valid_bsn(bsn), f"BUG: gegenereerd BSN {bsn} faalt 11-proef"
            return bsn
    raise RuntimeError("Niet gelukt om een geldig test-BSN te genereren in 100 pogingen")


@dataclass
class Persona:
    bsn: str
    voornaam: str
    achternaam: str
    geslacht: str  # 'M' | 'V' | 'X'
    geboortedatum: str  # ISO-8601: YYYY-MM-DD
    straat: str
    huisnummer: int
    postcode: str
    woonplaats: str
    nationaliteit: str = "NL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _random_birthdate(rng: random.Random, min_age: int = 18, max_age: int = 80) -> date:
    today = date(2026, 5, 1)  # repo-anker; productie gebruikt date.today()
    days = rng.randint(min_age * 365, max_age * 365)
    return today - timedelta(days=days)


def generate_persona(rng: random.Random, fake) -> Persona:
    """Maak één synthetische Persoon."""
    bsn = generate_test_bsn(rng)
    geslacht = rng.choice(["M", "V", "X"])
    if geslacht == "M":
        voornaam = fake.first_name_male()
    elif geslacht == "V":
        voornaam = fake.first_name_female()
    else:
        voornaam = fake.first_name_nonbinary()
    achternaam = fake.last_name()
    geboortedatum = _random_birthdate(rng)

    return Persona(
        bsn=bsn,
        voornaam=voornaam,
        achternaam=achternaam,
        geslacht=geslacht,
        geboortedatum=geboortedatum.isoformat(),
        straat=fake.street_name(),
        huisnummer=rng.randint(1, 999),
        postcode=fake.postcode(),
        woonplaats=fake.city(),
        nationaliteit="NL",
    )


def generate_personas(count: int, seed: int | None = None) -> Iterator[Persona]:
    """Yield `count` deterministisch gegenereerde personas."""
    rng = make_rng(seed)
    fake = make_faker(seed=seed)
    for _ in range(count):
        yield generate_persona(rng, fake)


def to_kafka_envelope(persona: Persona) -> dict[str, Any]:
    """Wrap persoon in event-envelope voor Kafka topic `uwv.persona.created`."""
    return envelope(persona.to_dict(), event_type="persona.created")


# CLI voor lokale tests
if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Genereer synthetische personas (test-BSN).")
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    for persona in generate_personas(args.count, seed=args.seed):
        print(json.dumps(persona.to_dict(), ensure_ascii=False))
