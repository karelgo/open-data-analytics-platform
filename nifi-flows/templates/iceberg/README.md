# NiFi flow templates — Iceberg variant

Status: **niet actief in deze implementatie** (we draaien Delta — zie
[ADR-0006](../../../docs/adr/0006-delta-chosen-for-this-implementation.md)).
Bewaard als template voor terug-switch.

## Verschil met Delta-variant

NiFi 2.x heeft een **native `PutIceberg`-processor**. Het ingest-pad kan
daardoor NiFi-only zijn:

```
GetSFTP / GetS3 → ValidateRecord → UpdateAttribute (PII) → PutIceberg → bronze
```

Geen tussenstap via Kafka nodig. Spark Streaming wordt dan alleen ingezet voor
silver/gold-transformations (CDC-applies, joins, MERGE INTO).

Bij switch terug naar Iceberg:
1. `platform-config.yaml`: `table_format: iceberg`.
2. `make render-catalogs && kubectl apply -k platform/09-trino/`.
3. NiFi-flows uit deze directory importeren (TODO fase 5+).
4. Spark streaming-job kan blijven, of vervangen door NiFi-only ingest.
