#!/usr/bin/env bash
# Run the same data pipeline without requiring a working Airflow executor.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOBS_DATE="${JOBS_DATE:-$(TZ=Europe/Amsterdam date +%F)}"
JOBS_MODE="${JOBS_MODE:-demo}"
JOBS_IMAGE="${JOBS_IMAGE:-odap/job-market:dev}"
case "$JOBS_MODE" in demo|live) ;; *) echo 'JOBS_MODE must be demo or live' >&2; exit 2 ;; esac
python3 -c 'import datetime,sys; datetime.date.fromisoformat(sys.argv[1])' "$JOBS_DATE"
JOBS_NAME="job-market-$(date +%s)"
kubectl -n odap-platform create job "$JOBS_NAME" --image="$JOBS_IMAGE" --dry-run=client -o json -- python /opt/job-market/runtime.py all --date "$JOBS_DATE" --mode "$JOBS_MODE" |
python3 -c '
import json,sys
job=json.load(sys.stdin)
spec=job["spec"]["template"]["spec"]
spec["serviceAccountName"]="spark-launcher"
spec["restartPolicy"]="Never"
job["spec"]["backoffLimit"]=0
job["spec"]["activeDeadlineSeconds"]=3600
c=spec["containers"][0]
c["resources"]={"requests":{"cpu":"100m","memory":"256Mi"},"limits":{"cpu":"1000m","memory":"1Gi"}}
c["env"]=[{"name":n,"valueFrom":{"secretKeyRef":{"name":"minio-s3-credentials","key":k}}} for n,k in [("S3_ACCESS_KEY","accessKey"),("S3_SECRET_KEY","secretKey")]]
c["env"].append({"name":"REQUESTS_CA_BUNDLE","value":"/etc/platform-ca/ca.crt"})
c["envFrom"]=[{"configMapRef":{"name":"job-market-settings"}},{"secretRef":{"name":"job-market-api-credentials","optional":True}}]
c["volumeMounts"]=[{"name":"platform-ca","mountPath":"/etc/platform-ca","readOnly":True}]
spec["volumes"]=[{"name":"platform-ca","configMap":{"name":"platform-ca-bundle"}}]
print(json.dumps(job))
' | kubectl -n odap-platform create -f -
echo "Started $JOBS_NAME; follow kubectl -n odap-platform logs -f job/$JOBS_NAME"
kubectl -n odap-platform wait --for=condition=complete "job/$JOBS_NAME" --timeout=3600s
# Materialized tables and tests now exist; rerun idempotent dataset/chart bootstrap.
kubectl -n odap-platform delete job superset-init superset-dashboards-init --ignore-not-found
kubectl apply -k "$ROOT/platform/12-superset"
kubectl -n odap-platform wait --for=condition=complete job/superset-init --timeout=600s
kubectl -n odap-platform wait --for=condition=complete job/superset-dashboards-init --timeout=600s
