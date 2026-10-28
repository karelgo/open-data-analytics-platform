"""MkDocs hooks: rewrite repo-relative links to GitHub blob URLs.

Veel docs (handbooken, use-cases, ADRs) verwijzen naar repo-bestanden
BUITEN de docs/-tree — `../../dbt/models/...`, `../../opa-policies-src/...`,
`../../platform/...`. Die werken in de repo (GitHub-blob preview) maar niet
in de gerenderde docs-site. Deze hook converteert ze tijdens de build naar
absolute GitHub-URLs, zonder de bronbestanden te wijzigen.

Geregistreerd via `hooks:` in mkdocs.yml.
"""
from __future__ import annotations

import re

REPO_BLOB = "https://github.com/karelgo/open-data-analytics-platform/blob/main/"
REPO_TREE = "https://github.com/karelgo/open-data-analytics-platform/tree/main/"

# Repo-root bestanden die GEKOPIEERD zijn naar binnen docs/ — links er naar
# vanuit elders binnen docs/ moeten to the interne kopie wijzen, niet naar
# de GitHub-blob URL van het origineel.
INTERNAL_REWRITE: dict[str, str] = {
    "SECURITY.md": "security.md",
}

# Top-level repo directories die NIET in de docs-tree zitten. Links naar
# deze paden — relatief of via ../../ — worden gerewrite naar GitHub-URLs.
EXTERNAL_REPO_ROOTS: tuple[str, ...] = (
    ".github",
    "data-generation",
    "examples",
    "dbt",
    "infrastructure",
    "nifi-flows",
    "opa-policies-src",
    "platform",
    "platform-overlays",
    "portal",
    "scripts",
    "spark-jobs",
    "tests",
    "ci",
    "logs",
)

# Top-level repo-root markdown-bestanden waarvoor we ook willen redirecten.
EXTERNAL_REPO_FILES: tuple[str, ...] = (
    "README.md",
    "WORKLOG.md",
    "LICENSE",
    "Makefile",
    "platform-config.yaml",
    "docker-compose.yml",
    "referentiearchitecture-odap-data-analytics.md",
    "requirements.md",
    "odap-platform-adr-0002-iceberg-vs-delta.md",
    "odap-platform-mapping-research.md",
    "odap-platform-master-agent-prompt-v2.md",
)


def _to_github_url(rel_path: str) -> str:
    # Splits anchor af zodat we de path-component apart kunnen valideren.
    if "#" in rel_path:
        path, anchor = rel_path.split("#", 1)
        anchor_suffix = f"#{anchor}"
    else:
        path, anchor_suffix = rel_path, ""

    base = REPO_TREE if path.endswith("/") else REPO_BLOB
    return f"{base}{path}{anchor_suffix}"


def _normalise(path: str) -> str:
    """Resolve `../`-segmenten zodat we het effectieve repo-pad krijgen."""
    parts: list[str] = []
    for segment in path.split("/"):
        if segment == "..":
            # `..` boven de root afkappen — repo-paden gaan nooit boven root.
            if parts:
                parts.pop()
        elif segment in ("", "."):
            continue
        else:
            parts.append(segment)
    suffix = "/" if path.endswith("/") and parts else ""
    return "/".join(parts) + suffix


def _is_external_repo_path(path: str) -> bool:
    """True als `path` (vanaf repo-root) buiten docs/ wijst naar een bestand of dir
    die we als GitHub-link willen renderen."""
    norm = _normalise(path)
    if not norm:
        return False
    # Anchor-only of section-only: niet rewriten.
    if norm.startswith(("http://", "https://", "mailto:", "#")):
        return False
    head = norm.split("/", 1)[0]
    if head in EXTERNAL_REPO_ROOTS:
        return True
    if head in EXTERNAL_REPO_FILES:
        return True
    # `docs/...` — verwijst naar onze eigen docs maar via absolute repo-pad.
    # Niet rewriten; mkdocs lost dit zelf op via relative resolution.
    return False


# Markdown-link patroon: `[label](target)` of `[label](target "title")`.
# We willen alleen de target rewriten als het naar externe repo-bestanden wijst.
MD_LINK = re.compile(r"\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")


def on_page_markdown(markdown: str, *, page, config, files):  # noqa: ARG001 — mkdocs API
    """Rewrite repo-relative links naar absolute GitHub-URLs.

    Een link wordt herschreven als zijn effectieve pad (na het oplossen van
    `../`-segmenten) naar een EXTERNAL_REPO_ROOTS/_FILES-target wijst. Andere
    links (intra-docs, externe URLs, ankers) blijven onveranderd.

    De resolutie houdt rekening with the positie van het bron-bestand: een
    use-case in docs/use-cases/uc01.md die `../../dbt/X` schrijft, resolveert
    tot `dbt/X` (twee niveaus omhoog → repo-root → omlaag in dbt/).
    """
    # Het pad van de huidige pagina relatief aan docs/.
    page_dir = page.file.src_path.replace("\\", "/").rsplit("/", 1)
    page_dir_path = page_dir[0] if len(page_dir) > 1 else ""

    def _rewrite(match: re.Match[str]) -> str:
        target = match.group(1)
        title = match.group(2) or ""

        # Niet rewriten als de link absolute is.
        if target.startswith(("http://", "https://", "mailto:", "tel:", "#", "/")):
            return match.group(0)

        # `docs/X.md` (vanuit een file die zelf in docs/ leeft) is een
        # auteur-fout uit gekopieerde repo-root-files (bv. security.md uit
        # SECURITY.md). Strip de `docs/`-prefix zodat mkdocs interne
        # resolutie werkt.
        if target.startswith("docs/"):
            target = target[len("docs/") :]
            return f"]({target}{title})"

        # `path/` of `../path/` — directory-link binnen docs/. Mkdocs zoekt
        # `path/index.html`; geef daarom expliciet `path/index.md` zodat de
        # interne validator klopt en de link werkt.
        if "?" not in target and "#" not in target and target.endswith("/"):
            # Skip externe paden — die zijn al door _is_external_repo_path
            # vóór deze rewrite afgehandeld in een later block (we passeren
            # door fall-through).
            pass  # handled by _is_external_repo_path below, otherwise:
            # Voor interne docs: voeg "index.md" toe.
            full_internal = (
                f"docs/{page_dir_path}/{target}" if page_dir_path else f"docs/{target}"
            )
            normalised_internal = _normalise(full_internal)
            if normalised_internal.startswith("docs/") and not _is_external_repo_path(
                normalised_internal[len("docs/") :]
            ):
                return f"]({target}index.md{title})"

        # Het effectieve pad relatief aan repo-root.
        # docs-pages leven onder docs/, dus de page_dir_path is bv. "use-cases".
        # Een link naar `../../dbt/X` resolveert dan tot `docs/use-cases/../../dbt/X`
        # = `dbt/X`. Voor een bare relative path zoals `portal/src/...` resolveert
        # die tot `docs/portal/src/...` — dat klopt niet, want het ECHTE bedoelde
        # pad is `portal/src/...` (repo-root-relative). We handelen dit af door:
        # 1. eerst proberen with the docs/-prefix (normaal relative resolution),
        # 2. als head dan in EXTERNAL_REPO_ROOTS valt na het strippen van leading
        #    docs-prefix, rewriten we.
        if page_dir_path:
            full = f"docs/{page_dir_path}/{target}"
        else:
            full = f"docs/{target}"

        normalised = _normalise(full)

        # Strip leading `docs/` (we zitten al binnen de docs-tree, alleen
        # externe targets interesseren ons). Wat overblijft moet starten met
        # een external repo root.
        if normalised.startswith("docs/"):
            stripped = normalised[len("docs/") :]
        else:
            stripped = normalised

        # Repo-root file die we INTERN hebben gerendered (SECURITY.md →
        # security.md). Vervang door interne link, niet GitHub-URL.
        if stripped in INTERNAL_REWRITE:
            # Bereken relatief pad van de huidige page to the gerenderde versie.
            depth = page_dir_path.count("/") + (1 if page_dir_path else 0)
            prefix = "../" * depth
            return f"]({prefix}{INTERNAL_REWRITE[stripped]}{title})"

        if not _is_external_repo_path(stripped):
            return match.group(0)

        return f"]({_to_github_url(stripped)}{title})"

    return MD_LINK.sub(_rewrite, markdown)
