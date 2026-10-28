# Jupyter: Dutch IT Job Market

The starter notebook `00_dutch_it_job_market.ipynb` follows the platform's single use case. It starts with the local SQLite output from `make jobs-demo`, then optionally queries the same job-market subject through Trino.

The platform kernel supplies `odap_lab.trino` and the user identity. Platform queries are disabled by default in the notebook so the offline section runs without a cluster. Enable only the sections authorized to your role: Gold for analyst perspectives, additional layers for approved research/engineering/stewardship.

The notebook covers snapshot history, source coverage, duplicate observations, overlapping domains, salary units and reported-versus-estimated values. Follow the same Gold table through Superset and OpenMetadata.

Kustomize bundles the notebook as `jupyter-starter-notebooks`. New users receive it in `work/starter`; existing user PVCs preserve their files. The always-mounted `~/starter/` directory contains the current version after deployment, even when `work/starter` was seeded by an earlier release.

See [the full walkthrough](../../docs/use-cases/dutch-it-job-market.md) and [runtime configuration](configmap-jupyterhub.yaml).
