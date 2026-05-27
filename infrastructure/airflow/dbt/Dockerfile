# ODAP dbt-trino image — bakt het hele dbt-project + dbt_packages in.
#
# Cosmos's ExecutionMode.KUBERNETES draait elke dbt-task in een verse pod.
# Mounten via ConfigMap is geen optie omdat dbt_packages > 1 MiB. Daarom
# bouwen we het project één keer in een image; rebuild bij dbt-wijzigingen.
#
# Build (vanuit repo-root):
#   docker build -t odap/dbt-trino:1.9.0 -f infrastructure/airflow/dbt/Dockerfile dbt
#   k3d image import odap/dbt-trino:1.9.0 -c odap-platform
#
# of via de Makefile:  make dbt-image
#
# SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
#
# Base-image: lokaal gebakken `odap/dbt-trino:1.9.0` (al aanwezig na bootstrap;
# upstream `ghcr.io/dbt-labs/dbt-trino:1.9.0` vereist auth bij anonymous pull).
FROM odap/dbt-trino:1.9.0

# dbt-fabricspark voor de UC-11 multi-platform demo (gold-marts op Fabric
# Lakehouse via Livy). 1.12 hangt op dbt-core>=1.8 wat compatibel is met de
# 1.9-base. Layer vóór de project-COPY zodat hercopiëren niet hoeft te
# reïnstalleren.
RUN pip install --no-cache-dir 'dbt-fabricspark==1.12.*'

# Project komt op /opt/odap/dbt/ — zelfde pad als waarvoor silver_factory en
# gold_factory's ProjectConfig zijn geconfigureerd (DBT_PROJECT_PATH).
WORKDIR /opt/odap/dbt

# Kopieer de dbt-project bron (incl. dbt_packages/ en profiles.yml.template).
# .dockerignore zorgt dat target/ en logs/ niet meegaan.
COPY . /opt/odap/dbt/

# profiles.yml is omgevings-specifiek — Cosmos genereert deze on-the-fly via
# TrinoCertificateProfileMapping. Verwijderen om verwarring te voorkomen.
RUN rm -f /opt/odap/dbt/profiles.yml || true

# Cosmos LoadMode.DBT_MANIFEST verwacht een vooraf gerenderd manifest.json.
# Dit is omgevings-specifiek (env_vars resolven), dus niet bakken in image.
# Het manifest blijft uit ConfigMap `dbt-manifest` komen via init container.

# Cosmos 1.6 KubernetesExecutionMode injecteert geen profiles.yml in de
# task-pod. Bakken we 'm zelf in: pre-rendered profile met env-var defaults
# voor host/user/port. cert=false omdat de cert-manager CA niet in dit image
# zit — in-cluster dev only.
COPY profiles.yml /root/.dbt/profiles.yml
