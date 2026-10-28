# OPA / Trino authorization

Policies for the single Dutch IT job-market example are generated from [opa-policies-src](../../opa-policies-src/). Run `make opa-bundle` before deployment. The Kustomize bundle includes role mapping, research-purpose restrictions, shared-metastore layer checks, contact masking and existing self-service grants.

`make opa-test` verifies the access decisions without a cluster. `tests/smoke/08-opa-decisions.sh` queries the deployed policy. See the [use-case walkthrough](../../docs/use-cases/dutch-it-job-market.md) for roles and data layers.
