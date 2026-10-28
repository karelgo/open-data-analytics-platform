# Current implementation scope

The platform has one active example: [Dutch IT Job Market](docs/use-cases/dutch-it-job-market.md).

The same Dutch vacancy observations flow through daily extraction, MinIO, Spark/Delta, Hive Metastore, Trino, dbt, Airflow, Superset, OpenMetadata and Jupyter. The portal, handbooks and learning modules follow this dataset across Data, Cloud, SAP, AI, Software and Security.

Run `make jobs-demo` and `make jobs-test` locally. On an existing cluster, build the runtime with `make jobs-image` and run `make jobs-run`. Live extraction requires explicit source access and a separate mode-pinned dataset. See the README and use-case guide for behavior, field semantics and limitations.

Previous rebranding plans and unrelated scenario instructions are archived under `docs/archive/legacy-examples/planning/` and do not define the active implementation.
