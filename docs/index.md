---
title: Dutch IT Job Market
---

# One platform, one data journey

The Open Data & Analytics Platform follows **Dutch IT vacancies** from a daily extraction to tested analytics. Explore Data, Cloud, SAP, AI, Software and Security through the same observations and history.

[Start the complete walkthrough](use-cases/dutch-it-job-market.md).

```bash
make jobs-demo
make jobs-test
```

The offline sample is deterministic and clearly marked synthetic. Live extraction uses configured job APIs/feeds and requires source access. Every stage keeps source provenance and distinguishes advertised salary from estimates.

| Explore | Purpose |
|---|---|
| [Use case and data dictionary](use-cases/dutch-it-job-market.md) | Setup, daily schedule, source coverage, model semantics and limitations |
| [Architecture](architecture/index.md) | How the same data crosses the platform |
| [Role handbooks](handbooks/README.md) | Analyst, engineering, stewardship and operations tasks |
| [Deployment](deployment-modes.md) | k3d, AKS and StackIT deployment |
| [Runbook](runbook.md) | Operate shared platform services |
| [Decisions](adr/index.md) | Why these platform technologies were selected |

Former unrelated examples are archived and excluded from active documentation.
