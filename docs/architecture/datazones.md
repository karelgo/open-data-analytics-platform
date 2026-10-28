# Data zones

All analytical layers use the `job_market` schema and separate Trino catalogs.

| Zone | Content | Access |
|---|---|---|
| Raw objects | Source responses and run manifests in `odap-bronze/job-market/raw/` | Restricted: responses may contain recruiter contact details |
| Bronze | `bronze.job_market.observations`: normalized source-job/day observations with provenance | Engineering and stewardship roles |
| Silver | Contact-redacted observations and one conservative duplicate group per day | Approved research, engineering and stewardship |
| Gold | Latest inventory and aggregates for demand, skills, salary, geography, work and source quality | Job-market analyst perspectives |

`is_synthetic` distinguishes offline fixtures from live data. Source observations remain separate from deduplicated snapshots. Daily absence does not prove job closure. Original salary units remain available even when no annual EUR comparison is possible.

See the [dictionary and semantics](../use-cases/dutch-it-job-market.md).
