# Request access to job-market data

Sign in to the portal with your platform account. Open **Request access**, select a specific asset and explain the job-market analysis or operational task.

Example asset: `trino.gold.job_market.mart_job_inventory`.

Example purpose: `labour_market_research`.

Example motivation: "Compare observed Cloud and Security vacancies by city, using deduplicated daily snapshots and reported salary coverage."

The OpenMetadata access bridge creates an approval task for the asset owner. After approval, the bridge can assign the corresponding `data_access:<catalog>.<schema>` realm role. An access request is not itself a grant. The deployed OPA rules remain authoritative, including any operational restrictions on underlying layers.

Business analyst views use Gold. Do not request raw source payloads simply to read a dashboard: raw descriptions can contain recruiter contact details. Approved engineering and stewardship tasks should specify the required scope and duration.

For a failed request, check the selected asset exists in OpenMetadata and contact the data steward. Do not work around denied access by copying restricted data through a colleague.

[Walkthrough and data dictionary](use-cases/dutch-it-job-market.md) · [Role handbooks](handbooks/README.md).
