---
title: Security Policy
description: Hoe kwetsbaarheden te rapporteren — NIS2-compliant disclosure flow.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Changes handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Security Policy

> Improvements #10 / R-NIS2-05.

Open Data & Analytics Platform neemt security en privacy serieus. Deze policy
beschrijft hoe je een kwetsbaarheid kunt melden, welke versies onderhouden
worden, en wat je van ons mag verwachten in de respons-flow.

---

## Supported versions

Dit is een **reference implementation**. Er zijn (nog) geen formele releases.
Onderhoud loopt on the `main`-branch:

| Branch | Status |
|---|---|
| `main` | actief — security-fixes binnen 7 dagen na bevestiging |
| feature-branches | best-effort |
| oudere commits | geen support |

Voor production-deployments wordt aangeraden een eigen fork te onderhouden
met versie-labels (semver).

---

## Een kwetsbaarheid melden

**Niet** via een publiek GitHub-issue. Gebruik in volgorde van voorkeur:

1. **GitHub Security Advisories** (preferred) —
   `Security` → `Report a vulnerability` op deze repo. Privé tot disclosure.
2. **E-mail** — `security@<jouw-organisatie>.nl` (vervang door echte contact bij fork).
   Voeg toe:
   - Beschrijving + impact
   - Reproductionstappen
   - Affected component(s) — bv. `platform/10-opa/`, `dbt/macros/`, `data-generation/`
   - Voorgestelde fix (optioneel)
   - Of je gepubliceerd wilt worden in de credits

Versleuteling: zie GitHub Security-advisory's ingebouwde TLS, of vraag onze
PGP-key via dezelfde e-mail.

### Wat verwacht je van ons?

| Stap | SLA |
|---|---|
| Acknowledgement | binnen 2 werkdagen |
| Triage + severity-assessment | binnen 5 werkdagen |
| Status-update | minstens elke 14 dagen |
| Fix gemerged | streefdatum afhankelijk van severity (zie tabel) |
| Coordinated disclosure | overlegd met melder |

### Severity → response-tijd (CVSS-based)

| CVSS | Voorbeeld | Fix-streefdatum |
|---|---|---|
| 9.0–10.0 (Critical) | Auth-bypass, RCE | ≤ 7 dagen |
| 7.0–8.9 (High) | Privilege-escalation, sensitive-data-leak | ≤ 30 dagen |
| 4.0–6.9 (Medium) | Info-disclosure, DoS | ≤ 60 dagen |
| 0.1–3.9 (Low) | Hardening-improvement | next-release |

---

## Scope

**In-scope** (graag melden):

- OPA Rego-policies in `opa-policies-src/` (incorrect deny/allow, bypass)
- dbt-macros en SQL-injection mogelijkheden
- Synthetische data-generators die per ongeluk echte data lekken
- Platform-manifests die over-privileged zijn (te brede SecretClass, RBAC)
- Container-images met kwetsbaarheden (door ons gepind)
- CI-workflows die secrets onbedoeld exposen
- Documentation-leaks (production-credentials in voorbeelden)

**Out-of-scope** (niet melden, of meld bij upstream-project):

- Stackable-, Trino-, Spark-, Kafka-, Postgres-CVE's — zie de upstream
  project-pages
- DDoS / denial-of-service via volume-attacks (dev-cluster aansprakelijk)
- Phishing / social engineering tegen contributors
- Issues die alleen reproduceerbaar zijn met `latest`-tag (we pinnen alles)

---

## Public disclosure

Kwetsbaarheden worden publiek gemaakt zodra:

- Een fix is uitgerold op `main` én in een tag, **OF**
- 90 dagen verstreken zijn sinds eerste melding (responsible-disclosure default)

We crediten de melder in de advisory tenzij anders gevraagd.

---

## Bekende beperkingen (intentioneel)

Deze repo is een **dev-referentie**, niet production-klaar. Items in
[`docs/runbook.md` § 11](docs/runbook.md) en
[`docs/improvements.md`](docs/improvements.md) zijn bekende gaps en geen
nieuwe vulnerabilities:

- Plaintext dev-secrets in `dev-secrets.yaml` (banner aanwezig)
- MinIO HTTP zonder TLS in dev
- Single-node OpenSearch zonder auth
- Geen NetworkPolicies (alleen namespace-isolation)
- `smoketest`-static-auth-user in Trino

Production-users zouden deze items eerst afdekken vóór deployment.

---

## Compliance

Deze policy ondersteunt:

- **R-NIS2-05** Vulnerability Disclosure-beleid
- **R-BIO-15** Vulnerability management
- **R-BIO-17** Secure SDLC

Zie [`docs/compliance-mapping.md`](docs/compliance-mapping.md) voor de
volledige mapping.

