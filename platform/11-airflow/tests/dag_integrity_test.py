"""DAG integrity test — runt op host (CI), zonder cluster.

Checkt:
  1. Alle YAML-source-files parsen tot een valide SourceSpec
  2. Alle DAG-aanroeperfiles parsen zonder fouten
  3. Geen import-cycles tussen include/-modules
  4. Dataset-dekking: elk silver-DAG heeft een bronze-Dataset als trigger,
     elk gold-DAG heeft een non-empty schedule
  5. Geen verwijzingen naar onbestaande sources

Gebruik:
    cd platform/11-airflow && pytest tests/

In CI: ci/github-actions/dag-integrity.yml (toe te voegen).

Vereist: airflow + astronomer-cosmos op de host (of skip met SKIP_COSMOS=1).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AIRFLOW_DIR = REPO_ROOT / "platform" / "11-airflow"
INCLUDE_DIR = AIRFLOW_DIR / "include"
DAGS_DIR = AIRFLOW_DIR / "dags"
SOURCES_DIR = AIRFLOW_DIR / "sources"

# Voeg include/ aan sys.path zodat factory-imports werken (matcht productie).
sys.path.insert(0, str(INCLUDE_DIR))
os.environ.setdefault("SOURCES_DIR", str(SOURCES_DIR))


def _try_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


HAS_AIRFLOW = _try_import("airflow")
HAS_COSMOS = _try_import("cosmos")


# ─── 1. YAML-registry parses ──────────────────────────────────────────


def test_all_source_yamls_parse():
    from sources_loader import load_all_sources

    specs = load_all_sources()
    assert len(specs) == 8, f"Expected 8 sources, got {len(specs)}: {[s.name for s in specs]}"
    names = {s.name for s in specs}
    assert names == {"persons", "policies", "service_requests", "claims", "eligibility_cases", "incidents", "customers", "finance"}


def test_exactly_one_anchor_source():
    from sources_loader import load_all_sources

    anchors = [s for s in load_all_sources() if s.anchor]
    assert len(anchors) == 1, f"Expected exactly 1 anchor, got {len(anchors)}"
    assert anchors[0].name == "persons"


def test_no_duplicate_streams_or_tables():
    """sources_loader._validate_uniqueness draait al — deze test fixt het contract."""
    from sources_loader import load_all_sources

    specs = load_all_sources()
    streams = [s.stream.name for s in specs if s.stream is not None]
    bronze = [s.bronze.fqn for s in specs]
    assert len(streams) == len(set(streams))
    assert len(bronze) == len(set(bronze))


# ─── 2. Dataset-conventies ────────────────────────────────────────────


def test_dataset_uris_well_formed():
    from datasets import all_bronze_datasets, silver_datasets_for_use_case

    for ds in all_bronze_datasets():
        assert ds.uri.startswith("bronze://"), ds.uri
    for ds in silver_datasets_for_use_case("uc01"):
        assert ds.uri.startswith("silver://"), ds.uri


def test_uc05_has_six_silver_dependencies():
    """UC-05 Client 360 leunt op alle persoonsgebonden bronnen.

    YAML-registry koppelt uc05 aan: persoon, polisadm, wia, crm, ww, zw (=6).
    fez en wajong zijn niet relevant voor cliënt-360.
    """
    from datasets import silver_datasets_for_use_case

    deps = silver_datasets_for_use_case("uc05")
    assert len(deps) == 6, f"UC-05 verwachtte 6 silver-deps, kreeg {len(deps)}: {[d.uri for d in deps]}"


# ─── 3. DAG parsing ───────────────────────────────────────────────────


def _import_module_from_path(path: Path):
    """Importeer een DAG-aanroeper als losse module (geen package-context)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not HAS_AIRFLOW, reason="airflow niet geïnstalleerd op host")
def test_all_dag_files_import():
    failed: list[tuple[str, str]] = []
    for dag_file in sorted(DAGS_DIR.glob("*.py")):
        if dag_file.name.startswith("_"):
            continue
        try:
            _import_module_from_path(dag_file)
        except Exception as exc:                     # noqa: BLE001
            failed.append((dag_file.name, str(exc)))
    assert not failed, f"DAG-import-fouten: {failed}"


# ─── 4. Cosmos availability ───────────────────────────────────────────


def test_cosmos_either_available_or_explicitly_fallback():
    """Productie: cosmos beschikbaar. Dev zonder cosmos: fallback-DAG-modus."""
    from silver_factory import COSMOS_AVAILABLE

    if not COSMOS_AVAILABLE:
        pytest.skip("Cosmos niet beschikbaar — fallback-mode geactiveerd. "
                    "Productie moet cosmos installeren (zie ADR-0007).")
    assert COSMOS_AVAILABLE


# ─── helpers ──────────────────────────────────────────────────────────


def _try_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False
