# NiFi flow templates — Delta variant

Status: **flow-design beschreven; geen geautomatiseerde import in fase 4.**

In de referentie-implementatie wordt de `uwv.<domain>.<event>` Kafka-pijp
voorlopig gevuld door [`data-generation/load_to_kafka.py`](../../../data-generation/load_to_kafka.py).
NiFi-flows volgen in fase 5+ — dit document legt vast hoe ze ontworpen zijn,
zodat de REST-API-deploy direct kan starten. **NiFi heeft géén publieke
Ingress meer** — flows zijn as-code (process-group JSON in deze repo) en
worden via `kubectl port-forward` geïmporteerd, niet via een UI.

## Flow-architectuur per domein

```
                                    ┌─────────────────────────────┐
                                    │ GetSFTP / GetS3 / InvokeHTTP │  (bron-mock)
                                    └──────────────┬──────────────┘
                                                   ▼
                                       ┌─────────────────────┐
                                       │  ValidateRecord     │
                                       │  (schema check)     │
                                       └────┬───────────┬────┘
                                            │ valid     │ invalid
                                            ▼           ▼
                                  ┌──────────────┐  ┌────────────────┐
                                  │ UpdateAttr.  │  │ PublishKafka   │
                                  │ PII-tagging  │  │ uwv.<d>.<e>.dlq│
                                  └──────┬───────┘  └────────────────┘
                                         ▼
                                  ┌──────────────────┐
                                  │ PublishKafka     │
                                  │ uwv.<domain>.<e> │
                                  └──────────────────┘
```

## Per-domein flows (voor fase 5)

| Flow | Bron-mock | Topic |
|---|---|---|
| `wia-ingest` | SyntheticHTTPSource (data-generation/k8s/seed-job) | `uwv.wia.aanvraag` |
| `ww-ingest` | idem | `uwv.ww.aanvraag` |
| `wajong-ingest` | idem | `uwv.wajong.dossier` |
| `polisadm-ingest` | idem | `uwv.polisadm.ikv` |
| `crm-ingest` | idem | `uwv.crm.contact` |
| `fez-ingest` | idem | `uwv.fez.uitkeringslast` |

## Delta-schrijven? Nee — Spark doet dat

In de Iceberg-stack zou NiFi via `PutIceberg` rechtstreeks naar het lakehouse
schrijven (zie Stackable demo). Voor Delta heeft NiFi **geen native processor**;
de referentie kiest daarom een tussenweg via Kafka. Zie
[`docs/adr/0006-delta-chosen-for-this-implementation.md`](../../../docs/adr/0006-delta-chosen-for-this-implementation.md)
§ R1.

## NiFi 2.x import-API

Geen publieke Ingress — eerst port-forwarden naar de NiFi-node, dan curl
tegen `https://localhost:8443/`.

```bash
# Terminal 1: port-forward (laat openstaan)
kubectl -n odap-platform port-forward svc/nifi-node-default 8443:8443

# Terminal 2: eenmalig — registreer NiFi Registry-bucket
curl -k -u "data.engineer:..." \
  -X POST https://localhost:8443/nifi-registry-api/buckets \
  -H "Content-Type: application/json" \
  -d '{"name":"flows-delta","description":"UWV reference flows (Delta variant)"}'

# Per flow: import process group via JSON
curl -k -u "data.engineer:..." \
  -X POST "https://localhost:8443/nifi-api/process-groups/<root-id>/process-groups/upload" \
  -F "process-group-import-json=@wia-ingest.json"
```

Concrete `*.json` flow-definities komen in fase 5 wanneer de bron-mocks
(SFTP / HTTP) ook bestaan.
