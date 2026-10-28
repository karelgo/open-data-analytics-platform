# Governance evidence for the job-market example

This page maps implemented controls to evidence. It does not assert legal compliance or certification.

| Concern | Implementation evidence |
|---|---|
| Synthetic/live separation | `is_synthetic` on observations; separate local outputs; S3 `job-market/mode.json` marker |
| Provenance | Source IDs/URLs, publication/observation dates, immutable attempt manifests and current pointers |
| Contact minimization | Analytical descriptions redact email/phone details; raw payloads remain restricted |
| Access control | Keycloak authentication and OPA Trino catalog/schema/purpose rules |
| Repeatability | Stable source identities, dated snapshots and idempotent daily partition replacement |
| Quality | Extractor unit tests and dbt key/domain/salary/uniqueness checks |
| Explainable classification | Deterministic vacancy taxonomy and skill rules in the extractor |
| Salary interpretation | Original units/currency/estimate flag retained, limited EUR annualization |
| Catalog and lineage | OpenMetadata definitions and dbt source-to-mart dependencies |

Review the [walkthrough and operational limits](use-cases/dutch-it-job-market.md) alongside actual source permissions and deployed configuration.
