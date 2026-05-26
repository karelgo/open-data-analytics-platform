# Exploration: Wachter — een agent-aangedreven log/trace-triage met human-in-the-loop fixes

> **Status: design-memo** in een nog te creëren branch `feat/wachter-explore`.
> Voorgesteld als derde "agent-lane" naast `19-nanitics-observatory`
> (build-time observability) en `17-multica` (dev-loop coordination).
>
> Promote to ADR-0009 zodra:
> - een minimale Wachter-detector op k3d een end-to-end ronde haalt
>   (OpenSearch log-event → Multica-issue → Approve-knop → kubectl-actie
>   met geverifieerde audit-trail);
> - de actie-allowlist door Platform Architect + CISO is goedgekeurd;
> - `docs/compliance-mapping.md` is uitgebreid met de AI Act / AVG-scope
>   van geautomatiseerde runtime-acties.

---

## TL;DR

**Wachter** ("watcher") is een nieuwe in-cluster applicatie die continu
de UDP-observability-streams afspeurt (Vector→OpenSearch logs,
Prometheus alerts, OpenTelemetry-spans, OpenMetadata DQ-events) en met
behulp van Nanitics-agents incidenten classificeert. Wat eruit komt is
**niet** een fix — het is een **Multica-issue** met een voorgestelde
remedie, een afgebakende *action plan*, en een knop "Approve". Pas na
menselijke goedkeuring voert een uitvoerings-daemon de actie daadwerkelijk
uit, en alleen acties uit een vooraf gedefinieerde allowlist.

Het scherpe testwoord dat alle drie agent-lanes scheidt is *waar draait
de agent en wat raakt-ie?*:

- **Nanitics**: cluster runt de agent, agent **bouwt** demo-tools en LLM-flows.
- **Multica**: laptop runt de agent, agent **schrijft code** voor de developer.
- **Wachter**: cluster runt de agent, agent **observeert het platform** en
  stelt **runtime-acties** voor die een mens moet goedkeuren.

Drie lanes — bouwen, schrijven, bewaken — één platform.

---

## Twee scopes, één codebase

De gebruiker heeft expliciet voor twee scopes gekozen die in één
applicatie samenkomen, maar als aparte profielen:

| Profiel | Wat de agent doet | Wat de agent **niet** doet |
|---|---|---|
| **Triage-only** (altijd-aan, default trust) | Logs/traces/alerts groeperen, root-cause hypothesen formuleren, runbook-link bijvoegen, een Multica-issue openen met label `triage` | Schrijven, executeren, of zelfs `kubectl get` aanroepen op productie |
| **Runtime-ops** (opt-in per actie, na approve) | Op approval een afgebakende kubectl/CLI-actie uitvoeren via een uitvoerings-daemon (pod restart, HPA scale, NiFi queue drain, Trino node draining) | Code wijzigen, Helm upgrades doen, secrets aanraken, persistente data muteren |

Concreet betekent dit dat **alle** detecties een triage-issue
opleveren. Een **deelverzameling** krijgt extra een `proposed-action`
(JSON-bijlage met exact 1 actie uit de allowlist). Alleen die
deelverzameling kan met Approve uitgevoerd worden; de rest is
informatief en de mens fixt zelf.

Deze splitsing is bewust — zie `## Risks` voor de motivatie.

---

## Waar Wachter in past

```
                    ┌──────────────────────── platform/14-monitoring ─────────────────┐
                    │                                                                  │
   Trino · Spark ──►│ Vector ──► OpenSearch (logs-*, logs-audit-*)             │
   NiFi · Airflow   │ kube-prometheus-stack ──► Prometheus + Alertmanager              │
   OPA · Postgres   │ OpenTelemetry collector ──► (Tempo/Jaeger — improvement #5.5)   │
                    │ OpenMetadata DQ-tests + lineage-events                           │
                    └──────────────────────────────┬───────────────────────────────────┘
                                                   │  pull (OS query) + push (AM webhook)
                                                   ▼
                                       ┌──────────────────────┐
                                       │  18-wachter (NEW)    │
                                       │  ─ FastAPI app       │
                                       │  ─ Nanitics SDK      │
                                       │  ─ ReAct/Reflexion   │
                                       │    triage-agents     │
                                       │  ─ action-planner    │
                                       └──────────┬───────────┘
                                                  │  POST /api/issues  (Multica REST)
                                                  ▼
                                       ┌──────────────────────┐
                                       │  17-multica          │
                                       │  Issue + action JSON │
                                       │  Status: awaiting-   │
                                       │  approval            │
                                       └──────────┬───────────┘
                                                  │  human Approve
                                                  ▼
                                       ┌──────────────────────┐
                                       │  wachter-runner      │
                                       │  (constrained k8s    │
                                       │   ServiceAccount,    │
                                       │   actions allowlist) │
                                       └──────────┬───────────┘
                                                  │  span tree
                                                  ▼
                                  19-nanitics-observatory  (audit + visualisatie)
```

Vier observaties uit dit plaatje die ontwerpkeuzes vastleggen:

1. **Wachter consumeert wat 14-monitoring al produceert.** Geen nieuwe
   instrumentatie. Verandering in observability-keuzes (bijv. ECS-format
   uit improvement #5.6) breekt Wachter niet harder dan welke andere
   consumer ook.
2. **Multica is de approval-UI.** We bouwen geen tweede frontend. Multica's
   `issue` + `agent_task_queue` schema dekt al dependency-graphs,
   comments, attachments en audit-velden — precies wat een
   change-management-stroom nodig heeft.
3. **Nanitics is de audit-viewer.** Iedere triage-run en iedere
   uitvoering streamt spans naar `/api/observatory/`. Dat geeft
   "voor/na/tijdens"-zicht zonder eigen logging-stack.
4. **De runner is geen agent.** Bewust. De LLM-redenering eindigt bij
   "voorstel-tot-actie"; uitvoering is een dom Python-script tegen een
   allowlist. De agent kan dus geen onbedoelde tweede actie introduceren
   tussen approval en uitvoering.

---

## Detectiepijplijn

Wachter draait drie soorten detectoren parallel; alle drie convergeren
op één gemeenschappelijk *incident-record*.

### Bron 1 — OpenSearch (logs)

Een scheduled task (elke 60s) draait een set saved searches op
`logs-*`:

| Saved search (voorbeeld) | Detectie |
|---|---|
| `severity:ERROR AND component:trino-coordinator` | Coordinator-fouten |
| `level:ERROR AND component:nifi AND message:*queue full*` | NiFi-backpressure |
| `level:WARN AND component:airflow AND task_state:failed` | DAG-task-failures |
| `kind:audit AND outcome:DENY AND policy:trino` | OPA-deny-spikes |

Per rolling window stuurt Wachter de tophits + counts naar de
**triage-agent** (Nanitics ReAct-flow): "geef incidenten terug met
component, severity, vermoedelijke oorzaak, voorgestelde *eerstvolgende*
actie".

### Bron 2 — Alertmanager (metrics)

Wachter abonneert zich als webhook-receiver in
`platform/14-monitoring/alertmanager-config.yaml` (parallel aan
Slack/PagerDuty, niet in plaats van). Ieder firing alert wordt
1-op-1 geconverteerd naar een incident-record. De bestaande
`runbook_url`-annotaties uit `prometheusrule.yaml` zijn de
*ground-truth* die we de agent als context meegeven, zodat de
voorstellen geen fantasie zijn maar een concrete runbook-stap citeren.

### Bron 3 — OTel traces

Vooruitlopend op improvement #5.5 (Distributed tracing — Jaeger/Tempo).
Wachter zoekt op:

- *spans met `error=true`* per service over rollend window;
- *p99-spans > N×median* per query-type (Trino) en per task (Spark);
- *broken parent/child trees* (signaal voor sampling-fouten of crash).

Tot Tempo er staat: deze bron is **stub** (returned `[]`); de hele
pipeline werkt zonder.

### Bron 4 — OpenMetadata (DQ + lineage)

`/api/v1/dataQuality/testCase/results` voor failed test-cases en
`/api/v1/lineage/events` voor onverwachte schema-drift. Mapt op
incidenten met component=`data` en severity afgeleid uit de
test-criticality.

### Het incident-record

Alle vier de bronnen produceren hetzelfde JSON-schema (compatibel met
Multica's `issue` + extra velden):

```json
{
  "fingerprint": "trino-coordinator-oom-2026-05-08T07:14",
  "title":       "Trino coordinator OOM-killed (3× in 10m)",
  "severity":    "warning|critical",
  "component":   "trino|spark|nifi|airflow|opa|postgres|data",
  "evidence":    [{"source":"opensearch","query":"...","hits":12}, ...],
  "runbook_url": "/docs/runbook.md#41-...",
  "hypothesis":  "Coordinator JVM-heap te laag voor concurrent ETL-workload",
  "proposed_action": {
    "kind": "kubectl_scale",
    "target": "trinocluster/trino",
    "args": {"replicas": 4},
    "dry_run_diff": "..."
  } // optional — pas gevuld als allowlist + confidence > drempel
}
```

`fingerprint` is deterministisch (component + truncated reden + uur)
zodat duplicaten in Multica geen tweede issue maken — ze hangen als
comment onder het bestaande issue.

---

## Van detectie naar Multica-issue

Wachter spreekt Multica's REST-API. Eerste contact:

```http
POST /api/issues
Authorization: Bearer <wachter-bot-token>
Content-Type: application/json

{
  "title":   "<incident.title>",
  "body":   "<markdown rendering of evidence + hypothesis + runbook>",
  "labels":  ["wachter", "triage", "<component>", "<severity>"],
  "metadata": {
    "fingerprint":     "<incident.fingerprint>",
    "proposed_action": {...}      // optional
  }
}
```

Daarna:

- *Triage-only incident* — labels `wachter`, `triage`, geen
  `proposed_action`. Status `open`, niemand toegewezen. Reviewer
  beslist en sluit zelf.
- *Runtime-ops voorstel* — extra label `awaiting-approval`. De
  `proposed_action` zit als JSON-attachment + leesbare diff in de body.
  Approve = label `approved` toevoegen, of een commentaar `/approve`
  posten (slash-command parsen we serverside zodat de UI-knop
  optioneel is).

Een aparte Wachter-component (`wachter-watcher`) polt
`/api/issues?label=approved&label=awaiting-execution` en draagt
goedgekeurde acties over aan de runner.

Waarom Multica als queue en niet zelf bouwen?

- Het schema bestaat al: `issue`, `issue_dependency`, `member`, `chat_message`,
  `inbox_item` — exact wat een approval-flow nodig heeft.
- Notificaties (e-mail, Slack via daemon) komen gratis mee.
- Toekomstige human-in-the-loop is uitbreidbaar in **dezelfde** UI:
  als een coding-agent ooit ook iets aan dit issue moet doen
  (bijv. "schrijf een dbt-test die dit voorkomt") is dat een
  bestaande Multica-flow.

---

## Van approval naar veilige uitvoering

`wachter-runner` is een aparte Deployment in `odap-platform`-namespace
met een **eigen ServiceAccount** waarvan de RBAC neerkomt op:

| Allowed verb | Allowed resources | Reden |
|---|---|---|
| `get`, `list`, `watch` | pods, deployments, statefulsets, hpa, jobs | Lezen voor diff/dry-run |
| `patch` | deployments/scale, statefulsets/scale, hpa | `kubectl scale` + `patch` |
| `delete` (pod only) | pods, **niet** PVCs/secrets | `kubectl delete pod` (controlled restart) |
| `create` | jobs (template-only, vanuit ConfigMap) | NiFi-flow-replay, Trino draining |

Geen `*`-wildcards. Geen `secrets`, geen `persistentvolumeclaims`,
geen `roles` of `rolebindings`. RoleBinding zit aan
`odap-platform`-namespace; cluster-scope is verboden.

De allowlist (versie 1) bevat exact deze 8 acties:

```yaml
# platform/18-wachter/actions/allowlist.yaml
- kind: kubectl_rollout_restart
  resources: [deployment, statefulset]
  namespaces: [odap-platform]
  rate_limit: 1 per 10m per resource

- kind: kubectl_scale
  resources: [hpa, deployment]
  bounds: { min_replicas: 1, max_replicas: 10 }

- kind: kubectl_delete_pod
  reasons: [crashloop, oomkilled]                # required field

- kind: trino_kill_query
  query_id_pattern: "^[a-z0-9_]+$"

- kind: spark_kill_application
  application_id_pattern: "^app-\\d{14}-\\d+$"

- kind: airflow_clear_task_instances
  dag_id_allowlist: <generated from Airflow API>

- kind: nifi_drain_queue
  connection_id_pattern: "^[0-9a-f-]{36}$"
  max_queue_size_mb: 500

- kind: opensearch_force_rollover
  index_pattern: "logs-*"
```

Alles wat *niet* in deze YAML staat krijgt nooit een
`proposed_action` van de planner-agent. Het is geen "wat de agent
liever niet doet" — het is "wat de runner überhaupt kan vinden in zijn
dispatch-tabel".

**Twee veiligheidsdetails:**

1. *Dry-run diff is verplicht.* Voor approve gemaakt wordt rendert
   Wachter een dry-run resultaat (`--dry-run=server` voor patch,
   `EXPLAIN`-equivalent voor Trino). Een actie zonder dry-run-diff
   krijgt nooit `awaiting-approval`.
2. *Audit hook is non-bypass.* Iedere uitvoering schrijft synchroon
   naar `logs-audit-*` (7 jaar bewaartermijn — ILM-policy in
   `14-monitoring/opensearch-ilm-job.yaml`). Mislukt het naar OpenSearch
   schrijven, dan vóórdat de actie loopt — dan annuleert de runner.
   Geen audit, geen actie.

---

## Compliance — wat moet er voor Wachter geregeld?

Beide bestaande agent-lanes hebben dit als open punt; Wachter brengt
het naar een hoger plan omdat hij **muteert**.

| Aspect | Status / Decision |
|---|---|
| **AI Act art. 50 (transparantie)** | Iedere Multica-issue gegenereerd door Wachter heeft prefix "[Wachter] …" en `agent_disclosure: true` in metadata. |
| **AI Act Annex III (high-risk)** | Argument: Wachter is geen besluitvormingssysteem over personen. Het *adviseert* operationele acties; mens beslist; en de allowlist zit op puur-technische k8s-objecten (geen BSN-data). Te bevestigen door Data Office. |
| **AVG art. 22 (geautomatiseerde besluitvorming)** | N.v.t. — Wachter raakt geen persoonsgegevens, raakt geen rechten van personen. Vermelden in `compliance-mapping.md`. |
| **AVG art. 32 (passende technische maatregelen)** | Allowlist + RBAC + audit-trail + dry-run + 4-ogen via Multica = expliciet *minimum-privilege*. |
| **R-BIO-20 (audit-bewaartermijn)** | 7 jaar via `audit-logs-policy.json` — bestaande beleid, geen wijziging nodig. |
| **NORA — controleerbaarheid** | Iedere actie heeft drie tracks: Multica issue, OpenSearch audit-log, Nanitics span-tree. Elk track is onafhankelijk en op zijn eigen manier doorzoekbaar. |
| **LLM-egress** | Wachter draait Nanitics → Azure AI Foundry. Zelfde lane als 16. *Belangrijk:* logs die naar de LLM gestuurd worden moeten gefilterd zijn op BSN/persoonsgegevens. We hergebruiken OpenMetadata's PII-classifier voor pre-filtering — zie open vraag #2. |

---

## Risks and sharp edges

1. **Twee agent-platforms zijn al verwarrend; drie is gevaarlijk.** Het
   *whose-laptop-runs-it*-frame uit de Multica-memo werkt hier niet —
   Wachter draait in-cluster, net als Nanitics. Het discriminerend
   begrip wordt **wat raakt-ie**: Nanitics raakt LLM-flows die in de
   pod blijven; Wachter raakt productie-objecten in de cluster. Onboarding
   moet die zin letterlijk leren.
2. **De allowlist is een politiek artefact.** Acht acties klinken
   weinig, maar elke toevoeging is een mini-CR — *waarom mag de bot dit
   ook?*. Dat is *feature*, niet *bug*. Discipline om het zo te houden.
3. **Approval-fatigue.** Als Wachter 50 issues per dag opent gaan
   reviewers reflexmatig approven. Mitigatie: (a) `fingerprint`
   dedup per uur; (b) per dag harde limiet op aantal `awaiting-approval`
   issues; (c) *boredom-test* in de planner-prompt: "als deze actie
   triviaal is, label-je 'm `auto-low-value` en stel je hem **niet**
   voor". De mens mag verveeld worden, niet de bot.
4. **Recursieve incidenten.** Een falende Wachter-pod kan zelf logs
   produceren die Wachter triggert om een issue over zichzelf te
   openen. Vangnet: incidenten met `component:wachter` mogen geen
   `proposed_action` krijgen. Triage-only.
5. **Multica WS-limitatie (zie 17-multica memo).** Live updates op het
   approval-issue werken in v1 niet zonder refresh. Mitigatie: stuur
   bij goedkeuring een Slack-notificatie via Alertmanager, zodat de
   reviewer niet hoeft te wachten met F5'en op de runner-output.
6. **Dual-write tussen Multica-DB en OpenSearch-audit.** Theoretisch
   kunnen die uiteenlopen. Mitigatie: OpenSearch is *bron van waarheid*
   voor audit; Multica is *bron van waarheid* voor approval-state.
   Hergebruik nooit Multica-DB als compliance-bewijs.
7. **Outbound LLM-egress vanuit cluster.** Iedere triage-run is een
   call naar Azure AI Foundry. In een geïsoleerde sovereign-omgeving
   kan dat onmogelijk worden. Plan: maak de LLM-keuze configureerbaar
   (LiteLLM-stijl, zoals de Nanitics-readme al suggereert voor
   deployment-style Azure OpenAI) zodat een lokaal model kan invallen.

---

## Phased delivery

### V1 — Triage-only (4–6 sprints)

Doel: één detector (Alertmanager-webhook), één bron (Prometheus
firing alerts), Multica-issues, geen acties. *Geen* runner. Bewijst
de pipeline.

Acceptatie:
- Alle bestaande alerts uit `prometheusrule.yaml` produceren een
  Multica-issue binnen 60 s.
- Issue bevat de runbook-link uit de annotation.
- Closed-issue-rate na een week ≥ 80 % (anders is signal/noise verkeerd).
- Zero `proposed_action`-velden in V1 — code-pad is er, allowlist is
  leeg, runner is niet gedeployed.

### V2 — OpenSearch + OTel, nog steeds triage-only

Tweede en derde detector erbij. OpenMetadata DQ-events. Verfijning van
fingerprinting; dedup met bestaande issues. Eerste evaluatie: hoeveel
unieke incidenten per dag? Hoeveel "fals*ies* die geen issue waard
waren"? Dat antwoord bepaalt of V3 doorgaat.

### V3 — Runtime-ops, allowlist met 2 acties

Begin minimaal: alleen `kubectl_rollout_restart` en `kubectl_scale`.
Runner deployen, RBAC strak, audit-pad aansluiten, dry-run-diff
verplicht. Eerste week alleen op niet-productie-namespace
(`odap-staging` als die bestaat, anders dev-cluster).

### V4 — Allowlist uitbreiden naar 8 acties + Trino/Spark/Airflow/NiFi

Eén actie per sprint, elk een mini-CR. ADR-0009 hier aan toe te
voegen.

### V5 — Eigen leerlus

Reviewers labelen approved-issues met `outcome: helpful | useless |
harmful`. Wachter gebruikt die labels in latere prompts (few-shot).
Buiten huidige scope, maar het is wel waar dit project naartoe
groeit.

---

## Open vragen

1. **Wie is de approver?** Single-reviewer? 4-ogen? Per-component
   eigenaar (`trino-team` etc.)? Multica's `member` + `team`-tabellen
   ondersteunen dat; we moeten gewoon kiezen.
2. **PII-filter op logs vóór ze naar het LLM gaan.** OpenMetadata heeft
   een classifier; bruikbaar als pre-processing? Of bouwen we een
   simpele regex (BSN, IBAN, e-mailadres) als 1e laag en classifier als
   2e? Conservatief: regex wint. Auditeerbaarheid > recall.
3. **Naam.** *Wachter* (NL, fits UWV) of iets eigens (ANSI-conform,
   internationaal). Voorkeursnaam vooraf vastleggen voor docs/branding
   redt later refactor-werk.
4. **Branch + nummer.** Voorstel: `platform/18-wachter/`,
   branch `feat/wachter-explore`. Past in de bestaande nummering en
   vervolgt op 17-multica.
5. **Slot in `improvements.md`.** Waarschijnlijk § 5.11 (volgende in de
   observability-reeks). Of een nieuw § 5.12 ("agentic ops"); §5.11
   is conservatiever en framet het als observability-uitbreiding,
   wat de scope correct begrenst.
6. **Multica-token-rotatie.** Wachter authenticeert als bot. Moet via
   Vault + External Secrets, niet als Kubernetes Secret. Open hoe dat
   schoon te maken — Multica heeft geen native OIDC (zie 17-multica
   memo).
7. **Wat als Multica down is?** Dan kan Wachter niets meer "indienen".
   Fallback: spool naar lokale PVC, retry exponential. Is dat genoeg of
   willen we bij Multica-outage een Slack-fallback?

---

## Success criteria voor promote-naar-ADR-0009

- [ ] `platform/18-wachter/` deployt op k3d, alle pods Ready.
- [ ] Alertmanager-firing alert produceert binnen 60 s een Multica-issue
      met label `wachter` en correct gefingerprintet.
- [ ] Een handmatig `awaiting-approval`-issue (allowlist actie:
      `kubectl_rollout_restart` op een dummy Deployment) leidt na
      Approve tot zichtbare audit-record in `logs-audit-*` met
      operator-identiteit (Multica-user) en bot-identiteit
      (Wachter-SA).
- [ ] Een handmatige poging om buiten de allowlist te executeren
      faalt met expliciete `action_not_in_allowlist`-fout en wordt
      óók geaudit.
- [ ] Nanitics-Observatory toont de span-tree van zowel de
      triage-run als de uitvoeringspoging.
- [ ] `docs/compliance-mapping.md` heeft een Wachter-sectie waarin
      AI Act art. 50, AVG art. 22, R-BIO-20 en NORA-controleerbaarheid
      expliciet zijn afgevinkt.
- [ ] `docs/runbook.md` heeft minstens één scenario "Wachter heeft
      iets gemarkeerd dat fout is" — fout-positief-procedure.

---

## Cross-references

- [`platform/19-nanitics-observatory/README.md`](../../platform/19-nanitics-observatory/README.md) — agent-runtime + trace-viewer; Wachter hergebruikt de SDK + Observatory.
- [`platform/17-multica/README.md`](../../platform/17-multica/README.md) — issue/task/agent-registry; Wachter is een API-client.
- [`platform/14-monitoring/README.md`](../../platform/14-monitoring/README.md) — bron van alle telemetrie.
- [`docs/explorations/multica-vs-nanitics.md`](./multica-vs-nanitics.md) — eerste lane-mapping; Wachter is daar het derde stipje op.
- [`docs/architecture.md`](../architecture.md) — observability-stack diagram (Vector / Prometheus / OTel).
- [`docs/improvements.md`](../improvements.md) — §5.5 (tracing), §5.6 (log-schema), §5.9 (alertmanager) zijn afhankelijk-of-versterkend.
- [`docs/runbook.md`](../runbook.md) — runbook-links zijn de *ground-truth* die Wachter aan de agent meegeeft.
