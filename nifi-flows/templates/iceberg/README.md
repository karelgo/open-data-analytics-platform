# Optional NiFi transport

The single supported example is [Dutch IT Jobs](../../../examples/dutch-it-jobs/). Its daily batch path is source API/feed → S3 → Spark Delta → dbt/Trino → Superset and OpenMetadata. NiFi and Kafka operators are disabled in the default platform and are not required by this example. No imported NiFi flow is provided.

If transport through NiFi is required later, forward the same normalized JSONL contract with its `job_id`, `snapshot_date` and source provenance; source permission, retries and manifest completion must be retained.
