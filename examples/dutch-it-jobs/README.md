# Dutch IT Job Market

One example follows Dutch IT vacancies through daily extraction, bronze observations,
silver normalization and deduplication, gold analytics, catalog, notebooks, and BI.
Domains are multi-label: **Data, Cloud, SAP, AI, Software, Security**.

## Run locally

Python **3.11+**, no third-party packages or cluster required:

```bash
python3 examples/dutch-it-jobs/job_market.py \
  --mode demo --date 2026-10-28 --days 7 \
  --output-dir examples/dutch-it-jobs/output
python3 -m unittest discover -s tests/unit -p 'test_job_market.py' -v
```

The fixtures describe 24 fictional vacancies on three fictional `.example` job
boards. All rows carry `is_synthetic=true`. Calendar-based cohorts create changing
daily observations, reposts, salary gaps, estimates, hourly freelance rates,
non-EUR salaries, junior/senior roles and Dutch/English requirements. They are not
representative Dutch labour-market statistics.

Each successful date partition contains:

```text
output/
  snapshot_date=2026-10-28/
    raw/<source>/<response files>   # restricted, unredacted source evidence
    normalized/observations.jsonl  # source observations; contacts redacted
    manifest.json                  # mode, counts, failures, bounds, taxonomy version
  dashboard.json                   # latest snapshot and daily trends
  job_market.sqlite                # observations, vacancies, snapshots, SQL views
```

Same-date reruns replace the partition; SQLite uses date + job keys. Failed
attempts go under `failed/snapshot_date=...` and never replace successful data.
Demo and live data require separate output directories.

Explore locally with SQLite:

```sql
SELECT * FROM daily_market ORDER BY snapshot_date;
SELECT title, company, city, work_mode, salary_year_min, salary_year_max
FROM latest_jobs ORDER BY salary_year_min DESC;
SELECT json_extract(payload, '$.contract_type') AS contract_type, COUNT(*)
FROM latest_jobs GROUP BY 1;
```

## Daily live extraction

The default live source is the Dutch Adzuna Jobs Search API. Register credentials
using the [official Adzuna documentation](https://developer.adzuna.com/overview),
then set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` in the environment. Source URLs and
credentials are never printed by the HTTP client. Source errors cause a nonzero
exit; live mode never falls back to fixtures.

```bash
# Set the two credentials through your environment/secret manager first.
python3 examples/dutch-it-jobs/job_market.py \
  --mode live --output-dir examples/dutch-it-jobs/output-live
```

The live snapshot date uses **Europe/Amsterdam**; `observed_at` stays UTC. Live
mode accepts today's date only: historical replay requires real archived source
responses. Six searches are paginated with configured limits, a timeout, pacing,
and bounded retries for 429/transient server/network failures. Manifests record
reported totals and page-limit truncation. Search coverage is a bounded sample;
the absence of a previously observed job never marks it closed.

[`sources.json`](sources.json) controls queries, pages, pacing and adapters. Add
operator-approved Dutch job board feeds and employer pages with these shapes:

```json
{"name":"my-dutch-feed","adapter":"rss","enabled":true,"approved":true,
 "country_code":"NL","url":"https://publisher.example/approved-jobs-feed"}
```

```json
{"name":"my-employer","adapter":"jsonld","enabled":true,"approved":true,
 "urls":["https://employer.example/careers/approved-job-detail"]}
```

These are configuration shapes, not functioning publishers. Configure real URLs
only after confirming collection and reuse permission. The JSON-LD adapter checks
`robots.txt` before fetching explicit detail pages and reads
[schema.org JobPosting](https://schema.org/JobPosting) fields; it does not discover
listing links. RSS/Atom reads the approved feed without fetching linked pages.
Country must be explicitly Dutch; missing title, usable job URL, or IT domain
excludes a row. RSS fields absent from the feed remain null.

## Interpretation

- `job_id` identifies one publisher listing; `duplicate_group_id` conservatively
  matches normalized employer + title + city. Missing employer/location prevents
  cross-publisher matching. All originals remain in observations.
- Deduplicated rows retain all sources and the union of domains/skills. A
  reported salary wins over an estimate, which wins over a missing salary;
  remaining ties prefer completeness and
  a stable listing key. This is a transparent heuristic, not guaranteed identity.
- Salary retains original currency/period/range and estimate flag. Only EUR annual
  or monthly amounts receive yearly equivalents (monthly × 12, without assumed
  holiday allowance). Hourly rates and foreign currencies are never mixed into
  annual salary averages. Dashboard salary averages also exclude estimates.
- Publication and observation dates are separate. No salary, province, work mode,
  hours, language or education requirement is invented when evidence is missing.
- Taxonomy `nl-it-rules-1` uses inspectable keywords with word boundaries. Domain
  totals overlap. Job text is data; extraction never executes publisher scripts.
- Common email/phone patterns are redacted from analytics text. Raw responses may
  contain contacts and must remain restricted with appropriate retention/access.

The platform walkthrough and deployment instructions are in
[`docs/use-cases/dutch-it-job-market.md`](../../docs/use-cases/dutch-it-job-market.md).
