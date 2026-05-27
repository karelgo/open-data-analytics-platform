"""Tests voor persona-generator."""

from __future__ import annotations

from generators.persona import generate_personas, is_valid_bsn


def test_generate_personas_count() -> None:
    out = list(generate_personas(50, seed=2026))
    assert len(out) == 50


def test_generate_personas_all_have_valid_bsn() -> None:
    for p in generate_personas(200, seed=2026):
        assert is_valid_bsn(p.bsn)


def test_generate_personas_deterministic_with_same_seed() -> None:
    a = list(generate_personas(20, seed=42))
    b = list(generate_personas(20, seed=42))
    assert [p.bsn for p in a] == [p.bsn for p in b]
    assert [p.voornaam for p in a] == [p.voornaam for p in b]


def test_generate_personas_different_with_different_seed() -> None:
    a = list(generate_personas(20, seed=1))
    b = list(generate_personas(20, seed=2))
    assert [p.bsn for p in a] != [p.bsn for p in b]


def test_persona_fields_present() -> None:
    for p in generate_personas(5, seed=1):
        d = p.to_dict()
        assert "bsn" in d and len(d["bsn"]) == 9
        assert d.get("voornaam")
        assert d.get("achternaam")
        assert d["geslacht"] in ("M", "V", "X")
        assert d["birth_date"].count("-") == 2
        assert isinstance(d["huisnummer"], int)
        assert d["nationaliteit"] == "NL"
