"""The same stage runner backs Airflow and the manual Kubernetes Job."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from datetime import date
from pathlib import Path

BASE = Path("/opt/job-market")
NAMESPACE = os.getenv("POD_NAMESPACE", "odap-platform")


def s3():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.getenv(
            "S3_ENDPOINT", "https://minio.odap-platform.svc.cluster.local:9000"
        ),
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.getenv("S3_REGION", "eu-nl-1"),
        verify=os.getenv("REQUESTS_CA_BUNDLE", "/etc/platform-ca/ca.crt"),
    )


def ensure_mode(client, bucket, mode):
    """Pin a lakehouse to demo or live; a transition requires a deliberate reset."""
    key = "job-market/mode.json"
    try:
        existing = json.loads(client.get_object(Bucket=bucket, Key=key)["Body"].read())
    except Exception as error:
        code = getattr(error, "response", {}).get("Error", {}).get("Code")
        if code not in ("NoSuchKey", "404", "NotFound"):
            raise
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps({"mode": mode}).encode(),
                ContentType="application/json",
                IfNoneMatch="*",
            )
            existing = {"mode": mode}
        except Exception as conflict:
            code = getattr(conflict, "response", {}).get("Error", {}).get("Code")
            if code not in ("PreconditionFailed", "412"):
                raise
            existing = json.loads(
                client.get_object(Bucket=bucket, Key=key)["Body"].read()
            )
    if existing.get("mode") != mode:
        raise RuntimeError(
            "This lakehouse already contains another data mode. Use a separate deployment or deliberately reset all job-market data before changing demo/live."
        )


def publish_extract(client, bucket, directory, snapshot_date, mode):
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest.get("status") != "success"
        or manifest.get("snapshot_date") != snapshot_date
        or manifest.get("mode") != mode
        or manifest.get("observation_count", 0) < 1
    ):
        raise RuntimeError(
            "Refusing to publish an unsuccessful, empty or mismatched extract manifest"
        )
    ensure_mode(client, bucket, mode)
    prefix = f"job-market/raw/snapshot_date={snapshot_date}/attempts/{uuid.uuid4().hex}"
    files = sorted(
        p for p in directory.rglob("*") if p.is_file() and p.name != "manifest.json"
    )
    files.append(directory / "manifest.json")
    for path in files:
        client.upload_file(str(path), bucket, f"{prefix}/{path.relative_to(directory)}")
    # This single atomic object update exposes only a fully uploaded immutable attempt.
    pointer = {
        "snapshot_date": snapshot_date,
        "mode": mode,
        "attempt_prefix": prefix,
        "observation_count": manifest["observation_count"],
    }
    client.put_object(
        Bucket=bucket,
        Key=f"job-market/raw/snapshot_date={snapshot_date}/current.json",
        Body=json.dumps(pointer).encode(),
        ContentType="application/json",
    )


def extract(args):
    output = Path("/tmp/job-market")
    client = s3()
    bucket = os.getenv("BRONZE_BUCKET", "odap-bronze")
    ensure_mode(client, bucket, args.mode)
    cmd = [
        "python",
        str(BASE / "example/job_market.py"),
        "--mode",
        args.mode,
        "--date",
        args.date,
        "--days",
        "1",
        "--output-dir",
        str(output),
    ]
    if os.getenv("JOB_MARKET_SOURCES"):
        cmd += ["--sources", os.environ["JOB_MARKET_SOURCES"]]
    subprocess.run(cmd, check=True)
    publish_extract(
        client, bucket, output / f"snapshot_date={args.date}", args.date, args.mode
    )
    print(f"Published successful {args.mode} extract for {args.date}", flush=True)


def bronze(args):
    import yaml
    from kubernetes import client, config

    config.load_incluster_config()
    api = client.CustomObjectsApi()
    template = yaml.safe_load((BASE / "job-market-bronze.yaml").read_text())
    name = f"job-market-{args.date.replace('-', '')}-{int(time.time())}"
    template["metadata"]["name"] = name
    for role in ("driver", "executor"):
        env = template["spec"][role]["podOverrides"]["spec"]["containers"][0]["env"]
        env.append({"name": "SNAPSHOT_DATE", "value": args.date})
    api.create_namespaced_custom_object(
        "spark.stackable.tech", "v1alpha1", NAMESPACE, "sparkapplications", template
    )
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        app = api.get_namespaced_custom_object(
            "spark.stackable.tech", "v1alpha1", NAMESPACE, "sparkapplications", name
        )
        phase = app.get("status", {}).get("phase")
        if phase == "Succeeded":
            api.delete_namespaced_custom_object(
                "spark.stackable.tech", "v1alpha1", NAMESPACE, "sparkapplications", name
            )
            return
        if phase == "Failed":
            raise RuntimeError(
                f"SparkApplication {name} failed; inspect its driver logs"
            )
        time.sleep(10)
    raise TimeoutError(f"SparkApplication {name} exceeded 30 minutes")


def transform(args):
    project = BASE / "dbt"
    subprocess.run(
        ["dbt", "build", "--project-dir", str(project), "--profiles-dir", str(project)],
        check=True,
    )
    subprocess.run(
        [
            "dbt",
            "docs",
            "generate",
            "--project-dir",
            str(project),
            "--profiles-dir",
            str(project),
        ],
        check=True,
    )
    client = s3()
    for artifact in ("manifest.json", "catalog.json", "run_results.json"):
        path = project / "target" / artifact
        for prefix in (f"dbt/job-market/{args.date}", "dbt/latest"):
            client.upload_file(
                str(path), os.getenv("META_BUCKET", "odap-meta"), f"{prefix}/{artifact}"
            )
    print("dbt models and tests passed; published lineage artifacts", flush=True)


def metadata(args):
    """Refresh catalog and lineage using the same mounted config as Airflow."""
    from kubernetes import client, config

    config.load_incluster_config()
    api = client.BatchV1Api()
    name = f"job-market-metadata-{int(time.time())}"
    env = []
    for envname, secret, key in [
        ("OM_JWT_TOKEN", "openmetadata-admin", "jwtToken"),
        ("TRINO_PASSWORD", "trino-static-users", "smoketest"),
        ("MINIO_SECRET_KEY", "minio-s3-credentials", "secretKey"),
        ("MINIO_ACCESS_KEY", "minio-s3-credentials", "accessKey"),
    ]:
        env.append(
            {
                "name": envname,
                "valueFrom": {"secretKeyRef": {"name": secret, "key": key}},
            }
        )
    env += [
        {
            "name": "MINIO_ENDPOINT",
            "value": "https://minio.odap-platform.svc.cluster.local:9000",
        },
        {"name": "REQUESTS_CA_BUNDLE", "value": "/etc/platform-ca/ca.crt"},
        {"name": "SSL_CERT_FILE", "value": "/etc/platform-ca/ca.crt"},
        {"name": "AWS_CA_BUNDLE", "value": "/etc/platform-ca/ca.crt"},
    ]
    script = (
        "envsubst < /config/trino-service.yaml > /tmp/trino.yaml && metadata ingest -c /tmp/trino.yaml && "
        "envsubst < /config/dbt-workflow.yaml > /tmp/dbt.yaml && metadata ingest -c /tmp/dbt.yaml && "
        "python /config/enrich_from_dbt_meta.py"
    )
    body = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 1200,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "metadata",
                            "image": "openmetadata/ingestion:1.12.8",
                            "command": ["bash", "-ec", script],
                            "env": env,
                            "volumeMounts": [
                                {
                                    "name": "config",
                                    "mountPath": "/config",
                                    "readOnly": True,
                                },
                                {
                                    "name": "ca",
                                    "mountPath": "/etc/platform-ca",
                                    "readOnly": True,
                                },
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "config",
                            "configMap": {"name": "openmetadata-platform-config"},
                        },
                        {"name": "ca", "configMap": {"name": "platform-ca-bundle"}},
                    ],
                }
            },
        },
    }
    api.create_namespaced_job(NAMESPACE, body)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        job = api.read_namespaced_job(name, NAMESPACE)
        if job.status.succeeded:
            api.delete_namespaced_job(name, NAMESPACE, propagation_policy="Background")
            return
        if job.status.failed:
            raise RuntimeError(f"Metadata refresh Job {name} failed; inspect Pod logs")
        time.sleep(10)
    raise TimeoutError(f"Metadata refresh Job {name} timed out")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage", choices=["extract", "bronze", "transform", "metadata", "all"]
    )
    parser.add_argument(
        "--date", required=True, type=lambda s: date.fromisoformat(s).isoformat()
    )
    parser.add_argument(
        "--mode", choices=["demo", "live"], default=os.getenv("JOB_MARKET_MODE", "demo")
    )
    args = parser.parse_args()
    if os.getenv("TABLE_FORMAT", "delta") != "delta":
        raise ValueError(
            "The Dutch IT jobs runtime currently requires TABLE_FORMAT=delta"
        )
    for stage, action in [
        ("extract", extract),
        ("bronze", bronze),
        ("transform", transform),
        ("metadata", metadata),
    ]:
        if args.stage in (stage, "all"):
            print(f"Starting {stage} {args.date} mode={args.mode}", flush=True)
            action(args)


if __name__ == "__main__":
    main()
