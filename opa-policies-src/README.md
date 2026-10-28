# Job-market access policies

`make opa-test` checks the policies; `make opa-bundle` copies them into the deployed ConfigMap. The source mapping is `data/role_mappings.json` and the tests use the same Stackable bundle path as the cluster.

- Existing business role IDs are retained for Keycloak compatibility; their example access is now limited to Gold job-market analytics with `purpose=labour_market_research`.
- Researchers may read sanitized Silver; data stewards and engineers have scoped quality/ingestion access. Raw object-store access uses a separate storage credential.
- All catalogs share Hive Metastore, so catalog names alone cannot enforce layer isolation. The policy also checks table allowlists: `observations` in Bronze, staging/canonical snapshots in Silver and the seven `mart_job_*` relations in Gold. Self-service grants cannot bypass this boundary.
- Unknown identities default to deny. The existing technical `smoketest` account remains the service identity for the illustrative deployment. Real deployments should configure their technical identities and Trino authentication separately.

The generated bundle and runtime source must stay aligned. Do not edit `platform/10-opa/policies/` directly.
