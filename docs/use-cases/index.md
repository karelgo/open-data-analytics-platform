---
title: Use cases — overzicht
description: 11 concrete business-flows met scope, doelbinding, CGM-entiteiten en datapad.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Wijzigingen handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Use cases

Elf use-case-specs onder [`use-cases/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/docs/use-cases),
elk met scope, CGM-entiteiten, doelbinding, AI-Act-classificatie en
Definition-of-Done-anchors.

| ID | Titel | Status | Domein | AI-Act |
|---|---|---|---|---|
| [UC-01](uc01-claims-funnel.md) | WIA-funnel-dashboard (DoD-anchor) | Mart aanwezig | AG/WIA | Laag |
| [UC-02](uc02-complex-cases-ai.md) | Wajong AI-ondersteuning (hoog-risico) | Placeholder | AG/Wajong | **Hoog** |
| [UC-03](uc03-fraud-risk.md) | WW-risico-screening (verboden-grens) | Placeholder + guard-test | WW | Verboden-grens |
| [UC-04](uc04-proactieve-tw.md) | Proactieve TW-eligibility | Mart aanwezig | TW | Beperkt |
| [UC-05](uc05-customer-360.md) | Klant-360 (gepseudonimiseerd) | Mart aanwezig | CRM | Laag |
| [UC-06](uc06-schadelast.md) | Schadelast-prognose 5 jaar | Mart aanwezig | FEZ | Laag |
| [UC-07](uc07-dq-policies.md) | DQ-dagrapport polisadministratie | Mart aanwezig | Polisadm | n.v.t. |
| [UC-08](uc08-capacity-planning-planning.md) | SMZ-capaciteitsplanning | Placeholder | SMZ | Beperkt |
| [UC-09](uc09-reintegration-effect.md) | Re-integratie-effectmeting | Mart aanwezig | Re-integratie | Beperkt |
| [UC-10](uc10-gegevensdiensten.md) | Gegevensdiensten-API | Placeholder | Cross-domein | n.v.t. |
| [UC-11](uc11-customer-journey.md) | Integrale Klantreis (event-stream + fasen) | Mart aanwezig · [walkthrough](uc11-customer-journey-walkthrough.md) | Cross-domein | Beperkt |

## UC-11 — speciale walkthrough

UC-11 heeft een aparte **demo-walkthrough** in
[uc11-customer-journey-walkthrough](uc11-customer-journey-walkthrough.md) —
stap-voor-stap rondleiding door alle platform-onderdelen, met directe
links naar de live UI's (portal, dbt-docs, OpenMetadata, Trino, Airflow,
Superset). Handig als presentatie-script of als onboarding-tour.

## Use-case format

Elke spec volgt dezelfde indeling:

- **Status in deze repo** — Volledig geïmplementeerd / Placeholder
- **Domein** — bv. AG/WIA, WW, CRM, FEZ
- **Risicoclassificatie** — laag / beperkt / hoog / verboden-grens (per AI Act)
- **AVG-grondslag** — art. 6 lid 1{a,b,c,d,e,f}
- **Bewaartermijn (gold)** — typisch 7 jaar (besluitvormingsdata)
- **Probleem** — waarom deze use-case bestaat
- **Doel** — wat moet er anders zijn na implementatie
- **Data** — bronnen, klassificaties, CGM-entiteiten
- **Architectuur-pad** — concrete repo-bestanden van bron → dashboard
- **DoD-anchor** — welk dbt-model + welke OPA-test bewijst dat het werkt
