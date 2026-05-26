"""Kafka peek-helpers for notebook demos.

Use this for streaming demos — read a few records from a topic, inspect the
payload, validate schema. Not meant for long-running consumers (which belong
in Spark Structured Streaming).
"""
from __future__ import annotations

import os
from typing import Iterable


def _bootstrap() -> str:
    return os.environ.get(
        "KAFKA_BOOTSTRAP_SERVERS",
        "kafka-broker-default-bootstrap.odap-platform.svc.cluster.local:9093",
    )


def consumer(topic: str, group_id: str | None = None):
    """Return a kafka-python ``KafkaConsumer`` subscribed to *topic*."""
    from kafka import KafkaConsumer

    return KafkaConsumer(
        topic,
        bootstrap_servers=_bootstrap(),
        group_id=group_id or "odap-lab-notebook",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=5000,
    )


def peek(topic: str, n: int = 10) -> list[bytes]:
    """Return up to *n* raw payloads from *topic* — non-blocking-ish."""
    c = consumer(topic)
    out: list[bytes] = []
    for msg in c:
        out.append(msg.value)
        if len(out) >= n:
            break
    c.close()
    return out


def list_topics() -> Iterable[str]:
    """Return the currently visible topics on the cluster."""
    from kafka import KafkaConsumer

    c = KafkaConsumer(bootstrap_servers=_bootstrap())
    try:
        return sorted(c.topics())
    finally:
        c.close()
