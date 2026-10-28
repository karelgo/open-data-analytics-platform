FROM python:3.11-slim
RUN pip install --no-cache-dir dbt-core==1.11.16 dbt-trino==1.9.3 boto3==1.35.99 kubernetes==31.0.0 requests==2.32.3 PyYAML==6.0.2
WORKDIR /opt/job-market
COPY examples/dutch-it-jobs/job_market.py examples/dutch-it-jobs/sources.json /opt/job-market/example/
COPY examples/dutch-it-jobs/fixtures/ /opt/job-market/example/fixtures/
COPY dbt/ /opt/job-market/dbt/
COPY infrastructure/job-market/profiles.yml /opt/job-market/dbt/profiles.yml
COPY infrastructure/job-market/runtime.py /opt/job-market/runtime.py
COPY platform/08-spark/apps/job-market-bronze.yaml /opt/job-market/job-market-bronze.yaml
ENV DBT_PROFILES_DIR=/opt/job-market/dbt PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/opt/job-market/runtime.py"]
