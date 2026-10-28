# Open Data & Analytics Platform — Makefile
#
# Top-level targets per master agent prompt §5. De zware logica zit in
# scripts/*.sh; deze Makefile orchestreert alleen.
#
# Conventie: alle targets zijn idempotent en herstartbaar.

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

CLUSTER_NAME ?= odap-platform
PLATFORM_CONFIG := platform-config.yaml

# Deployment mode (k3d|aks). Override per invocation:  make deploy MODE=aks
# The mode propagates to every script via --mode and to helm value selection
# via scripts/lib/mode.sh. Default = k3d (developer-laptop scenario).
MODE ?= k3d

# Lees TABLE_FORMAT uit platform-config.yaml (yq). Fallback naar 'delta'.
TABLE_FORMAT ?= $(shell command -v yq >/dev/null 2>&1 && yq -r '.platform.table_format // "delta"' $(PLATFORM_CONFIG) 2>/dev/null || echo delta)

export TABLE_FORMAT
export CLUSTER_NAME
export MODE
export DEPLOYMENT_MODE := $(MODE)

##@ General

.PHONY: help
help: ## Toont deze help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

.PHONY: print-config
print-config: ## Print de actieve platform-configuratie
	@echo "MODE         = $(MODE)"
	@echo "CLUSTER_NAME = $(CLUSTER_NAME)"
	@echo "TABLE_FORMAT = $(TABLE_FORMAT)"
	@echo "Platform config:"
	@cat $(PLATFORM_CONFIG)

##@ Lifecycle

.PHONY: cluster
cluster: ## Maak lokale cluster aan (k3d, idempotent). Voor aks: gebruik 'make aks-up'.
	@case "$(MODE)" in \
	  k3d)  bash scripts/cluster.sh ;; \
	  aks)  echo "MODE=aks: gebruik 'make aks-up' om een AKS cluster te provisionen"; exit 1 ;; \
	  *)    echo "Onbekende MODE='$(MODE)' (verwacht k3d, aks)"; exit 1 ;; \
	esac

.PHONY: bootstrap
bootstrap: ## Installeer Helm-charts: cert-manager, MinIO, Postgres, Keycloak, Stackable operators (mode-aware)
	bash scripts/bootstrap.sh --mode=$(MODE)

.PHONY: deploy-platform
deploy-platform: render-catalogs portal-image jobs-image jupyter-image nanitics-image multica-daemon-image ## Deploy alle platform-manifests onder platform/ (mode-aware)
	bash scripts/deploy-platform.sh --mode=$(MODE)

.PHONY: deploy
deploy: ## End-to-end deploy: cluster + bootstrap + platform + portal + smoke (mode-aware). For MODE=aks see 'make aks-all'.
	@if [ "$(MODE)" = "aks" ]; then \
	  echo "MODE=aks: use 'make aks-all' (provisions infra + bootstrap + deploy + smoke)"; exit 1; \
	fi
	bash scripts/full-deploy.sh --mode=$(MODE)

.PHONY: portal-image
portal-image: ## Build odap/portal:dev (Astro static site + nginx) en importeer in lokale cluster (k3d). Skipped voor aks.
	@if [ "$(MODE)" = "aks" ]; then echo "[portal-image] mode=aks: image wordt gepublished via 'make aks-portal-publish' (ConfigMap)"; exit 0; fi
	docker build -f portal/Dockerfile -t odap/portal:dev .
	k3d image import odap/portal:dev -c $(CLUSTER_NAME)
	@echo "[portal-image] image gebouwd + geïmporteerd (mode=$(MODE))."

.PHONY: jupyter-image
jupyter-image: ## Build odap/jupyter-kernel:dev (JupyterLab + odap_lab helper) en importeer in lokale cluster. Skipped voor aks.
	@if [ "$(MODE)" = "aks" ]; then echo "[jupyter-image] mode=aks: image wordt uit een registry getrokken — skip lokale build"; exit 0; fi
	docker build -t odap/jupyter-kernel:dev -f infrastructure/jupyter/kernel-python/Dockerfile .
	k3d image import odap/jupyter-kernel:dev -c $(CLUSTER_NAME)
	@echo "[jupyter-image] image gebouwd + geïmporteerd (mode=$(MODE))."

.PHONY: nanitics-image
nanitics-image: ## Build odap/nanitics-observatory:dev (FastAPI + nanitics SDK + watcher). Skipped voor aks.
	@if [ "$(MODE)" = "aks" ]; then echo "[nanitics-image] mode=aks: skip — pull from registry (TODO: aks-nanitics-publish target)"; exit 0; fi
	bash platform/19-nanitics-observatory/build-and-load.sh
	@echo "[nanitics-image] image gebouwd + geïmporteerd (mode=$(MODE))."

.PHONY: multica-daemon-image
multica-daemon-image: ## Build odap/multica-daemon:dev (multica CLI + Codex bound to Foundry). Skipped voor aks.
	@if [ "$(MODE)" = "aks" ]; then echo "[multica-daemon-image] mode=aks: skip — pull from registry (TODO: aks-multica-daemon-publish target)"; exit 0; fi
	bash platform/20-multica-daemon/build-and-load.sh
	@echo "[multica-daemon-image] image gebouwd + geïmporteerd (mode=$(MODE))."

.PHONY: multica-bootstrap
multica-bootstrap: ## Na een Multica-reset: workspace + labels seeden, watcher configmap bijwerken, watcher rollen. Idempotent.
	bash scripts/multica-bootstrap.sh $(MULTICA_BOOTSTRAP_ARGS)

.PHONY: portal-publish-dbt-docs
portal-publish-dbt-docs: dbt-docs-offline portal-image ## Genereer dbt-docs → bake in portal-image → rollout (k3d)
	kubectl -n odap-platform rollout restart deploy/portal
	kubectl -n odap-platform rollout status  deploy/portal --timeout=120s
	@echo "[portal-publish-dbt-docs] klaar — open https://platform.odap.local:8443/dbt-docs.html"

.PHONY: render-catalogs
render-catalogs: ## Render Trino-catalog templates op basis van platform-config.yaml
	python3 scripts/render-trino-catalogs.py

.PHONY: opa-test
opa-test: ## Run opa fmt + opa test op opa-policies-src/ (data wrapped onder Stackable bundle-pad)
	@command -v opa >/dev/null 2>&1 || { echo "opa niet geïnstalleerd — zie scripts/doctor.sh"; exit 1; }
	opa fmt --diff opa-policies-src/trino/
	@python3 scripts/opa-test-data-wrap.py --dst /tmp/opa-test-data.json
	opa test opa-policies-src/trino/ /tmp/opa-test-data.json -v

.PHONY: opa-bundle
opa-bundle: opa-test ## Build OPA-bundle: sync rego + data naar platform/10-opa/policies/
	bash scripts/build-opa-bundle.sh

.PHONY: dbt-image
dbt-image: jobs-image ## Compatibility alias: the job-market runtime includes dbt

.PHONY: om-bridge-image
om-bridge-image: ## Build odap/om-access-bridge:dev en importeer in k3d
	bash platform/18-om-access-bridge/build-and-load.sh

.PHONY: deploy-om-bridge
deploy-om-bridge: om-bridge-image ## Deploy de OM→Keycloak access-bridge (ADR-0008) — incl. Keycloak-client + OM-subscription setup
	@if ! kubectl -n odap-platform get secret om-access-bridge-secret >/dev/null 2>&1; then \
	  echo "[deploy-om-bridge] om-access-bridge-secret bestaat nog niet — bootstrappen met dev-placeholders."; \
	  echo "                    Voor production: zie platform/18-om-access-bridge/secret.yaml"; \
	  OM_JWT="$$(kubectl -n odap-meta get secret openmetadata-admin -o jsonpath='{.data.jwtToken}' 2>/dev/null | base64 -d)"; \
	  if [ -z "$$OM_JWT" ]; then echo "[deploy-om-bridge] WAARSCHUWING: openmetadata-admin secret nog niet aanwezig — OM_ADMIN_TOKEN wordt placeholder; /api/request zal 500 geven tot bridge re-deployed met token."; OM_JWT="REPLACE-WITH-JWT-FROM-openmetadata-admin-SECRET"; fi; \
	  kubectl -n odap-platform create secret generic om-access-bridge-secret \
	    --from-literal=KEYCLOAK_CLIENT_SECRET='odap-dev-only-CHANGE-ME-om-access-bridge-secret' \
	    --from-literal=OM_WEBHOOK_SECRET='odap-dev-only-CHANGE-ME-om-webhook-secret' \
	    --from-literal=OM_ADMIN_TOKEN="$$OM_JWT"; \
	elif ! kubectl -n odap-platform get secret om-access-bridge-secret -o jsonpath='{.data.OM_ADMIN_TOKEN}' 2>/dev/null | grep -q .; then \
	  echo "[deploy-om-bridge] secret bestaat maar OM_ADMIN_TOKEN ontbreekt — patchen."; \
	  OM_JWT="$$(kubectl -n odap-meta get secret openmetadata-admin -o jsonpath='{.data.jwtToken}' | base64 -d)"; \
	  kubectl -n odap-platform patch secret om-access-bridge-secret --type=json -p="[{\"op\":\"add\",\"path\":\"/data/OM_ADMIN_TOKEN\",\"value\":\"$$(printf %s "$$OM_JWT" | base64)\"}]"; \
	fi
	@if [ -d "platform-overlays/$(MODE)/18-om-access-bridge" ]; then \
	  kubectl apply -k "platform-overlays/$(MODE)/18-om-access-bridge"; \
	else \
	  kubectl apply -k platform/18-om-access-bridge/; \
	fi
	kubectl -n odap-platform rollout status deploy/om-access-bridge --timeout=120s
	@echo "[deploy-om-bridge] Idempotent setup van Keycloak-client + OM-subscription"
	bash scripts/setup-om-bridge-keycloak.sh
	bash scripts/setup-om-bridge-subscription.sh

.PHONY: seed
seed: ## Load the single synthetic Dutch IT job-market example into the cluster
	bash scripts/seed.sh

.PHONY: om-fix-search-mapping
om-fix-search-mapping: ## Patch OS-mappings zodat OM 1.12 Explore-UI werkt (idempotent).
	bash scripts/om-fix-search-mapping.sh

.PHONY: test
test: smoke ## Alias voor smoke tests

.PHONY: smoke
smoke: ## Run smoke tests onder tests/smoke/
	bash scripts/run-smoke-tests.sh

.PHONY: alert-test
alert-test: ## Verstuur een synthetische alert (default warning). Action: warning|critical|resolve. Voorbeeld: 'make alert-test ACTION=critical'
	bash scripts/alert-test.sh --mode=$(MODE) $(ACTION)

.PHONY: alert-test-resolve
alert-test-resolve: ## Resolveer de synthetische test-alert (verstuurt zelfde alert met endsAt in verleden)
	bash scripts/alert-test.sh --mode=$(MODE) resolve

.PHONY: e2e
e2e: ## Validate the Dutch IT job-market cluster pipeline
	bash tests/e2e/job-market-flow.sh

.PHONY: clean
clean: ## Verwijder de k3d-cluster
	bash scripts/clean.sh

##@ Quality

.PHONY: lint
lint: lint-yaml lint-rego lint-python ## Run alle linters

.PHONY: lint-yaml
lint-yaml: ## yamllint over platform/ + infrastructure/
	yamllint -c ci/yamllint.yaml platform/ infrastructure/ || true

.PHONY: lint-rego
lint-rego: opa-test ## Validate the source policy using the deployed data layout

.PHONY: lint-python
lint-python: ## Lint job-market extractor and Spark ingestion
	ruff check examples/dutch-it-jobs/ spark-jobs/job_market_bronze.py infrastructure/job-market/

.PHONY: dbt-parse
dbt-parse: ## Parse the job-market dbt graph without warehouse access
	@test -f dbt/profiles.yml || cp dbt/profiles.yml.template dbt/profiles.yml
	@if [ -n "$(DBT)" ]; then \
	  $(DBT) parse --project-dir dbt --profiles-dir dbt; \
	else \
	  docker run --rm --entrypoint dbt "$(JOBS_IMAGE)" parse --project-dir /opt/job-market/dbt --profiles-dir /opt/job-market/dbt; \
	fi

# dbt-binary: prefereer dbt-core (Python) — die ondersteunt `docs generate
# --static`. dbt-fusion (Rust-rewrite) ondersteunt het commando nog niet,
# dus als die als eerste op PATH staat valt de target stil. Override met
# `DBT=/pad/naar/dbt make dbt-docs`.
DBT ?= $(shell test -x $$HOME/.dbt-core-venv/bin/dbt && echo $$HOME/.dbt-core-venv/bin/dbt || command -v dbt)

# CA-bundle voor TLS-verify naar Trino. dbt-trino's `cert:`-setting wordt op
# sommige paden genegeerd; via REQUESTS_CA_BUNDLE/SSL_CERT_FILE gebeurt het
# zeker. Pad komt overeen with the fallback in dbt/profiles.yml.
TRINO_TLS_CERT_PATH ?= $$HOME/.odap-platform-ca.crt

.PHONY: dbt-docs
dbt-docs: ## dbt docs generate --static, en sync naar portal/public/dbt-docs.html (vereist live Trino)
	cd dbt && $(DBT) deps && \
	  REQUESTS_CA_BUNDLE=$(TRINO_TLS_CERT_PATH) SSL_CERT_FILE=$(TRINO_TLS_CERT_PATH) \
	  $(DBT) docs generate --static
	@mkdir -p portal/public
	@cp dbt/target/static_index.html portal/public/dbt-docs.html
	@echo "[dbt-docs] portal/public/dbt-docs.html bijgewerkt — open in dev via http://localhost:4321/dbt-docs.html"

.PHONY: dbt-docs-offline
dbt-docs-offline: ## dbt docs (lineage-only, geen warehouse-introspection) — werkt zonder cluster
	cd dbt && $(DBT) deps && $(DBT) docs generate --static --no-compile --empty-catalog
	@mkdir -p portal/public
	@cp dbt/target/static_index.html portal/public/dbt-docs.html
	@echo "[dbt-docs-offline] portal/public/dbt-docs.html bijgewerkt (zonder kolom-types — lineage werkt wel)."
	@echo "  Open direct in browser:  file://$(PWD)/portal/public/dbt-docs.html"
	@echo "  Of via portal dev-server: http://localhost:4321/dbt-docs.html"

##@ Maintenance

.PHONY: doctor
doctor: ## Check vereiste tooling op host (mode-aware: doctor MODE=aks)
	@bash scripts/doctor.sh --mode=$(MODE)

.PHONY: forward
forward: ## Start kubectl port-forwards voor UI's (zie scripts)
	@bash scripts/port-forward.sh

.PHONY: trust-ca
trust-ca: ## Importeer ~/.config/odap/ca/tls.crt in de macOS System Keychain (idempotent, eenmalig per machine)
	@bash scripts/trust-ca.sh

##@ AKS (Azure)

.PHONY: aks-up
aks-up: ## Provision AKS cluster via Terraform (existing dev-stackable-rg)
	bash scripts/azure/aks-up.sh

.PHONY: aks-context
aks-context: ## Set kubectl context to AKS cluster (az aks get-credentials)
	bash scripts/azure/aks-context.sh

.PHONY: aks-bootstrap
aks-bootstrap: ## Install helm charts + Stackable operators on AKS
	bash scripts/azure/aks-bootstrap.sh

.PHONY: aks-deploy
aks-deploy: render-catalogs ## Deploy platform manifests on AKS
	bash scripts/azure/aks-deploy.sh

.PHONY: aks-smoke
aks-smoke: ## Run smoke tests against the AKS context
	DEPLOYMENT_MODE=aks PLATFORM_DOMAIN=example.com bash scripts/run-smoke-tests.sh

.PHONY: aks-all
aks-all: aks-up aks-context aks-bootstrap aks-deploy aks-smoke ## End-to-end AKS lifecycle: up + context + bootstrap + deploy + smoke

##@ StackIT (SKE)

# Auto-export KUBECONFIG to the terraform-generated kubeconfig when targets
# below are invoked. Recipes inherit this so bootstrap/deploy/smoke don't
# need a manual `export KUBECONFIG=...` first.
STACKIT_KUBECONFIG := $(shell test -f infrastructure/stackit/terraform/kubeconfig.yaml && \
  cd infrastructure/stackit/terraform && terraform output -raw kubeconfig_absolute_path 2>/dev/null)

.PHONY: stackit-up
stackit-up: ## Provision StackIT SKE cluster + reserved Floating IP via Terraform
	bash scripts/stackit/ske-up.sh

.PHONY: stackit-context
stackit-context: ## Print `export KUBECONFIG=...` for the stackit cluster (use with `eval $(make stackit-context)`)
	@echo "export KUBECONFIG=\"$$(cd infrastructure/stackit/terraform && terraform output -raw kubeconfig_absolute_path)\""

.PHONY: stackit-bootstrap
stackit-bootstrap: ## Install helm charts + Stackable operators on StackIT SKE
	KUBECONFIG="$(or $(KUBECONFIG),$(STACKIT_KUBECONFIG))" bash scripts/stackit/ske-bootstrap.sh

.PHONY: stackit-deploy
stackit-deploy: render-catalogs ## Deploy platform manifests on StackIT SKE
	KUBECONFIG="$(or $(KUBECONFIG),$(STACKIT_KUBECONFIG))" bash scripts/stackit/ske-deploy.sh

.PHONY: stackit-portal-publish
stackit-portal-publish: ## Build portal/dist (if missing) + ship as ConfigMaps to SKE, then roll the Deployment
	KUBECONFIG="$(or $(KUBECONFIG),$(STACKIT_KUBECONFIG))" bash scripts/stackit/portal-publish.sh

.PHONY: stackit-smoke
stackit-smoke: ## Run smoke tests against the StackIT context
	KUBECONFIG="$(or $(KUBECONFIG),$(STACKIT_KUBECONFIG))" DEPLOYMENT_MODE=stackit PLATFORM_DOMAIN=example.com bash scripts/run-smoke-tests.sh

.PHONY: stackit-all
stackit-all: stackit-up stackit-bootstrap stackit-deploy stackit-portal-publish stackit-smoke ## End-to-end StackIT lifecycle: cluster + helm + platform + portal + smoke (~40 min from cold)

.PHONY: stackit-hibernate
stackit-hibernate: ## Hibernate the SKE cluster — deallocates worker nodes, control plane sleeps. Cluster + Floating IP + PVCs preserved.
	stackit ske cluster hibernate udp-stackit --project-id 442855d5-308d-4e93-95ec-e1a959d6846a -y

.PHONY: stackit-wake
stackit-wake: ## Wake a hibernated SKE cluster — workers scale back up to node_minimum. Takes ~3-5 min.
	stackit ske cluster wakeup udp-stackit --project-id 442855d5-308d-4e93-95ec-e1a959d6846a -y

.PHONY: stackit-status
stackit-status: ## Show SKE cluster state (HEALTHY / HIBERNATED / RECONCILING / ...)
	@stackit ske cluster describe udp-stackit --project-id 442855d5-308d-4e93-95ec-e1a959d6846a -o json \
	  | jq -r '"state:        \(.status.aggregated)\nhibernated:   \(.status.hibernated)\nk8s version:  \(.kubernetes.version)\nnode pools:   \(.nodepools | length)\negress IP(s): \(.status.egressAddressRanges | join(", "))"'

.PHONY: stackit-down
stackit-down: ## Destroy the SKE cluster (PVCs lost, Floating IP + DNS preserved; come back via `make stackit-up && make stackit-all`)
	@echo "About to terraform-destroy the SKE cluster udp-stackit."
	@echo "  KEPT:    Floating IP 188.34.84.39 (prevent_destroy → DNS records stay valid)"
	@echo "  LOST:    all PVCs (postgres, minio, opensearch, prometheus data, ...), Keycloak realm, certs"
	@echo "  COST:    only Floating IP fee (~€1–5/mo) while down; 0 compute"
	@echo "  RECOVER: \`make stackit-up && make stackit-all\` (~40 min from cold)"
	@echo
	@read -p "Type 'destroy' to confirm: " confirm && [ "$$confirm" = "destroy" ] || { echo "aborted"; exit 1; }
	terraform -chdir=infrastructure/stackit/terraform destroy \
	  -target=stackit_ske_cluster.cluster \
	  -auto-approve

.PHONY: aks-stop
aks-stop: ## Stop AKS cluster (deallocate nodes — cost-saving, reversible)
	bash scripts/azure/aks-stop.sh

.PHONY: aks-start
aks-start: ## Resume a stopped AKS cluster
	bash scripts/azure/aks-start.sh

.PHONY: aks-hibernate
aks-hibernate: ## Stop + snapshot all PVC disks + delete disks (cuts stopped-state cost ~50%)
	bash scripts/azure/aks-hibernate.sh down

.PHONY: aks-wake
aks-wake: ## Restore PVC disks from hibernate snapshots + start cluster
	bash scripts/azure/aks-hibernate.sh up

.PHONY: aks-cost
aks-cost: ## Show currently provisioned Azure resources + monthly cost estimate
	bash scripts/azure/aks-hibernate.sh status

.PHONY: aks-down
aks-down: ## terraform destroy — full teardown, zero ongoing cost
	bash scripts/azure/aks-down.sh

##@ AKS — unified lifecycle (one-shot scripts)

.PHONY: aks-up-all
aks-up-all: ## Provision EVERYTHING: AKS + bootstrap + deploy + smoke
	bash scripts/azure/aks-up-all.sh

.PHONY: aks-stop-all
aks-stop-all: ## Stop AKS to save compute cost (full teardown: make aks-down-all)
	bash scripts/azure/aks-stop-all.sh

.PHONY: aks-down-all
aks-down-all: ## terraform destroy ALL: AKS + VNet + certs (€0 after)
	bash scripts/azure/aks-down-all.sh

.PHONY: aks-pf
aks-pf: ## Start kubectl port-forward to AKS ingress (127.0.0.2:8443 → *.odap-platform.cloud)
	@bash scripts/azure/aks-pf.sh start

.PHONY: aks-pf-stop
aks-pf-stop: ## Stop the AKS port-forward
	@bash scripts/azure/aks-pf.sh stop

.PHONY: aks-portal-publish
aks-portal-publish: ## Build portal/dist (if missing) + ship it as a ConfigMap to AKS, then roll the Deployment
	bash scripts/azure/portal-publish.sh

##@ Dutch IT Job Market (the single platform example)

PYTHON ?= python3
JOBS_DATE ?= $(shell date +%F)
JOBS_OUTPUT ?= examples/dutch-it-jobs/output
JOBS_LIVE_OUTPUT ?= examples/dutch-it-jobs/output-live
JOBS_IMAGE ?= odap/job-market:dev
export JOBS_IMAGE

.PHONY: jobs-demo jobs-live jobs-test jobs-image jobs-run job-market-image
jobs-demo: ## Run seven synthetic daily extracts and local SQLite analytics (no cluster or credentials)
	$(PYTHON) examples/dutch-it-jobs/job_market.py --mode demo --date "$(JOBS_DATE)" --output-dir "$(JOBS_OUTPUT)"

jobs-live: ## Collect one date from configured live sources (requires source credentials)
	$(PYTHON) examples/dutch-it-jobs/job_market.py --mode live --date "$(JOBS_DATE)" --output-dir "$(JOBS_LIVE_OUTPUT)"

jobs-test: ## Run deterministic extraction, quality, history and failure tests without network
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_job_market*.py' -v

jobs-image: ## Build packaged extraction/dbt runtime; import into local k3d when MODE=k3d
	docker build -t "$(JOBS_IMAGE)" -f infrastructure/job-market/Dockerfile .
	@if [ "$(MODE)" = "k3d" ]; then k3d image import "$(JOBS_IMAGE)" -c "$(CLUSTER_NAME)"; fi

job-market-image: jobs-image ## Alias for jobs-image

jobs-run: ## Run the complete extraction -> Spark -> dbt -> metadata pipeline on an existing cluster
	bash scripts/job-market-cluster.sh
