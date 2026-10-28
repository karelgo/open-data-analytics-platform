#!/usr/bin/env python3
"""Daily Dutch IT vacancy observations; offline demonstration and explicit live mode.

Python 3.11+ standard library only. Raw payloads are restricted source evidence;
normalized observations redact common contact details and preserve unknown values.
An observation is evidence of seeing a listing, never proof a job remains open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TAXONOMY_VERSION = "nl-it-rules-1"
SNAPSHOT_TIMEZONE = ZoneInfo("Europe/Amsterdam")
DOMAINS = {
    "data": r"\b(data[ -](?:engineer|analyst|analist|scientist|architect)|analytics|databricks|snowflake|dbt|etl|bi developer|power bi|data platform)\b",
    "cloud": r"\b(cloud|azure|aws|gcp|kubernetes|terraform|devops|platform engineer|site reliability)\b",
    "sap": r"\b(sap|abap|s/4hana|s4hana|fiori|bw/4hana)\b",
    "ai": r"\b(ai|artificial intelligence|kunstmatige intelligentie|machine learning|mlops|llm|generative ai|genai|pytorch|tensorflow)\b",
    "software": r"\b(software|developer|ontwikkelaar|programmeur|backend|frontend|full.stack|java|javascript|typescript)\b|(?<!\w)(?:c#|\.net)(?!\w)",
    "security": r"\b(security|cyber|cybersecurity|soc analyst|pentest|iam|siem|informatiebeveiliging|ethical hack)\b",
}
SKILLS = {
    "Python": r"\bpython\b", "SQL": r"\bsql\b", "Spark": r"\b(?:apache )?spark\b",
    "dbt": r"\bdbt\b", "Kafka": r"\bkafka\b", "Airflow": r"\bairflow\b",
    "Databricks": r"\bdatabricks\b", "Snowflake": r"\bsnowflake\b",
    "Power BI": r"\bpower\s?bi\b", "Azure": r"\bazure\b", "AWS": r"\baws\b",
    "GCP": r"\bgcp\b|google cloud", "Kubernetes": r"\bkubernetes\b",
    "Terraform": r"\bterraform\b", "Docker": r"\bdocker\b", "Linux": r"\blinux\b",
    "SAP": r"\bsap\b", "ABAP": r"\babap\b", "S/4HANA": r"\bs/?4hana\b",
    "Fiori": r"\bfiori\b", "PyTorch": r"\bpytorch\b", "TensorFlow": r"\btensorflow\b",
    "LLM": r"\bllms?\b", "RAG": r"\brag\b", "MLOps": r"\bmlops\b",
    "Java": r"\bjava\b", "JavaScript": r"\bjavascript\b", "TypeScript": r"\btypescript\b",
    "React": r"\breact\b", "C#": r"(?<!\w)c#(?!\w)", ".NET": r"(?<!\w)\.net\b",
    "Go": r"\bgolang\b", "Rust": r"\brust\b", "SIEM": r"\bsiem\b",
    "IAM": r"\biam\b", "Splunk": r"\bsplunk\b", "Sentinel": r"\bsentinel\b",
    "ISO 27001": r"\biso\s?27001\b", "CISSP": r"\bcissp\b",
}
PERIODS = {"year": "year", "annual": "year", "yearly": "year", "jaar": "year",
           "month": "month", "monthly": "month", "maand": "month",
           "hour": "hour", "hourly": "hour", "uur": "hour"}


class SourceError(RuntimeError):
    """Sanitized source failure: do not include credential-bearing request URLs."""


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def plain(value):
    parser = Text()
    parser.feed(str(value or ""))
    return re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()


def redact(value):
    text = plain(value)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    # Dutch mobile and fixed-line formats; do not match salary ranges or dates.
    text = re.sub(r"(?<!\w)(?:\+31\s?(?:\(0\))?|0031\s?|0)(?:6(?:[ .-]?\d){8}|[1-5,7-9]\d[ .-]?\d(?:[ .-]?\d){6})(?!\d)", "[phone removed]", text)
    return text


def stable_id(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def key_text(value):
    return re.sub(r"[^\w]+", " ", str(value or "").casefold()).strip()


def canonical_url(value):
    if not value:
        return None
    parts = urlsplit(str(value))
    if parts.scheme not in ("https", "http") or not parts.hostname:
        return None
    params = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(params), ""))


def snapshot_today():
    return datetime.now(SNAPSHOT_TIMEZONE).date()


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if result >= 0 and result < float("inf") else None
    except (TypeError, ValueError):
        return None


def timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def normalize(record, source, snapshot_date, observed_at, synthetic=False):
    """Normalize a common adapter record; return None for non-NL/non-IT rows."""
    country = str(record.get("country_code") or "").upper()
    if country not in {"NL", "NETHERLANDS", "NEDERLAND"}:
        return None
    title = redact(record.get("title"))
    company = redact(record.get("company")) or None
    city = redact(record.get("city")) or None
    description = redact(record.get("description"))
    if not title:
        return None
    text = title + " " + description + " " + plain(record.get("skills"))
    domains = [name for name, pattern in DOMAINS.items() if re.search(pattern, text, re.IGNORECASE)]
    if not domains:
        return None
    url = canonical_url(record.get("url"))
    if not url:
        return None
    source_id = str(record.get("id") or url or stable_id(title + "|" + str(company) + "|" + str(city)))
    job_id = stable_id(source + "|" + source_id)
    # Missing employers/locations are unsafe for cross-source matching.
    group_key = "|".join(map(key_text, (company, title, city))) if company and city else job_id
    period = PERIODS.get(str(record.get("salary_period") or "").lower(), "unknown")
    currency = str(record.get("salary_currency") or "").upper() or None
    low, high = number(record.get("salary_min")), number(record.get("salary_max"))
    if low is not None and high is not None and low > high:
        low = high = None
    factor = 12 if period == "month" else 1 if period == "year" else None
    estimated = record.get("salary_is_estimated") in (True, 1, "1", "true", "True")
    seniority = record.get("seniority")
    if not seniority:
        for level, pattern in [("intern", r"\b(intern|stage|stagiair)\b"), ("junior", r"\b(junior|starter|graduate)\b"), ("lead", r"\b(lead|principal|staff|head)\b"), ("senior", r"\bsenior\b"), ("medior", r"\b(medior|mid.level)\b")]:
            if re.search(pattern, title, re.IGNORECASE):
                seniority = level
                break
    work_mode = record.get("work_mode")
    if not work_mode:
        if re.search(r"\b(hybrid|hybride)\b", text, re.IGNORECASE):
            work_mode = "hybrid"
        elif re.search(r"\b(fully remote|volledig remote|volledig thuiswerken)\b", text, re.IGNORECASE):
            work_mode = "remote"
        elif re.search(r"\b(on.?site|op kantoor)\b", text, re.IGNORECASE):
            work_mode = "onsite"
    language = record.get("language")
    if not language:
        if re.search(r"\b(nederlands vereist|dutch required|vloeiend nederlands)\b", text, re.IGNORECASE):
            language = "Dutch required"
        elif re.search(r"\b(english required|fluent english)\b", text, re.IGNORECASE):
            language = "English required"
    education = plain(record.get("education")) or None
    if not education:
        match = re.search(r"\b(hbo|wo|mbo|bachelor|master|phd)\b", text, re.IGNORECASE)
        education = match.group().upper() if match else None
    return {
        "job_id": job_id, "source": source, "source_job_id": source_id,
        "canonical_url": url, "duplicate_group_id": stable_id(group_key),
        "snapshot_date": snapshot_date, "observed_at": observed_at,
        "title": title, "company": company, "city": city,
        "province": plain(record.get("province")) or None, "country_code": "NL",
        "latitude": number(record.get("latitude")), "longitude": number(record.get("longitude")),
        "description_text": description or None, "domains": domains,
        "skills": [skill for skill, pattern in SKILLS.items() if re.search(pattern, text, re.IGNORECASE)],
        "seniority": seniority, "employment_type": record.get("employment_type"),
        "contract_type": record.get("contract_type"), "work_mode": work_mode,
        "hours_min": number(record.get("hours_min")), "hours_max": number(record.get("hours_max")),
        "salary_min": low, "salary_max": high, "salary_currency": currency,
        "salary_period": period, "salary_is_estimated": estimated,
        "salary_year_min": low * factor if currency == "EUR" and factor and low is not None else None,
        "salary_year_max": high * factor if currency == "EUR" and factor and high is not None else None,
        "language": language, "education": education,
        "published_at": timestamp(record.get("published_at")), "expires_at": timestamp(record.get("expires_at")),
        "is_synthetic": synthetic,
    }


class HttpClient:
    """Bounded retries and per-request pacing; failures never expose secret URLs."""
    def __init__(self, config):
        self.agent = config.get("user_agent", "ODAP-Dutch-IT-Jobs/1.0")
        self.interval = max(0, float(config.get("request_interval_seconds", 1)))
        self.timeout = float(config.get("timeout_seconds", 30))
        self.retries = int(config.get("retries", 3))
        self.last_request = 0.0
        self.robots = {}

    def get(self, url, accept="application/json"):
        if urlsplit(url).scheme != "https":
            raise SourceError("Only HTTPS source URLs are accepted")
        for attempt in range(self.retries + 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                request = Request(url, headers={"User-Agent": self.agent, "Accept": accept})
                with urlopen(request, timeout=self.timeout) as response:
                    # Avoid unexpectedly loading a feed or page larger than 10 MB.
                    payload = response.read(10_000_001)
                    if len(payload) > 10_000_000:
                        raise SourceError("Source payload exceeds 10 MB limit")
                    return payload.decode("utf-8")
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise SourceError(f"Source HTTP status {error.code}") from None
                retry_after = error.headers.get("Retry-After", "")
                delay = min(60, float(retry_after)) if retry_after.isdigit() else min(30, 2 ** attempt)
                time.sleep(delay)
            except (URLError, TimeoutError, OSError, UnicodeError):
                if attempt == self.retries:
                    raise SourceError("Source network, timeout, or encoding failure") from None
                time.sleep(min(30, 2 ** attempt))
        raise SourceError("Source retry limit reached")

    def allow_page(self, url):
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots:
            # Fail closed when robots cannot be retrieved; no RobotFileParser.read()
            # because it bypasses this client's timeout and pacing.
            rules = self.get(origin + "/robots.txt", "text/plain")
            parser = RobotFileParser()
            parser.parse(rules.splitlines())
            self.robots[origin] = parser
        if not self.robots[origin].can_fetch(self.agent, url):
            raise SourceError("Page disallowed by robots.txt")


def adzuna_record(item):
    location = item.get("location") or {}
    area = location.get("area") or []
    return {
        "id": item.get("id"), "url": item.get("redirect_url"), "title": item.get("title"),
        "company": (item.get("company") or {}).get("display_name"),
        "city": location.get("display_name"), "province": area[1] if len(area) > 1 else None,
        "country_code": "NL", "description": item.get("description"),
        "latitude": item.get("latitude"), "longitude": item.get("longitude"),
        "salary_min": item.get("salary_min"), "salary_max": item.get("salary_max"),
        "salary_currency": "EUR", "salary_period": "year",
        "salary_is_estimated": item.get("salary_is_predicted", "0"),
        "employment_type": item.get("contract_time"), "contract_type": item.get("contract_type"),
        "published_at": item.get("created"),
    }


def extract_adzuna(source, client, raw_dir):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise SourceError("Adzuna requires ADZUNA_APP_ID and ADZUNA_APP_KEY")
    if source.get("country", "nl").lower() != "nl":
        raise SourceError("The Dutch jobs example only accepts Adzuna country nl")
    max_pages, page_size = int(source.get("max_pages_per_query", 2)), int(source.get("results_per_page", 50))
    if not (1 <= max_pages <= 100 and 1 <= page_size <= 50):
        raise SourceError("Invalid Adzuna pagination limits")
    records, queries = [], []
    for index, query in enumerate(source.get("queries", [])):
        fetched, total, exhausted = 0, None, False
        for page in range(1, max_pages + 1):
            params = urlencode({"app_id": app_id, "app_key": app_key, "what": query,
                                "results_per_page": page_size, "sort_by": "date"})
            body = client.get(f"https://api.adzuna.com/v1/api/jobs/nl/search/{page}?{params}")
            data = json.loads(body)
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise SourceError("Adzuna response has no results array")
            write_json(raw_dir / f"query-{index + 1}-page-{page}.json", data)
            total = data.get("count")
            items = data["results"]
            records.extend(adzuna_record(item) for item in items)
            fetched += len(items)
            if len(items) < page_size or (isinstance(total, (int, float)) and fetched >= total):
                exhausted = True
                break
        queries.append({"query": query, "fetched": fetched, "reported_count": total,
                        "page_limit_reached": not exhausted})
    if not queries:
        raise SourceError("Adzuna queries must not be empty")
    return records, {"queries": queries, "bounded_search": True,
                     "truncated": any(q["page_limit_reached"] for q in queries)}


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.buffer = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self.capture = True
            self.buffer = []

    def handle_data(self, value):
        if self.capture:
            self.buffer.append(value)

    def handle_endtag(self, tag):
        if tag == "script" and self.capture:
            self.documents.append(json.loads("".join(self.buffer)))
            self.capture = False


def postings(node):
    if isinstance(node, list):
        for child in node:
            yield from postings(child)
    elif isinstance(node, dict):
        types = node.get("@type", [])
        if "JobPosting" in (types if isinstance(types, list) else [types]):
            yield node
        for child in node.values():
            if isinstance(child, (dict, list)):
                yield from postings(child)


def schema_record(item, page_url):
    location = item.get("jobLocation") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address") or {}
    country = address.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    salary = item.get("baseSalary") or item.get("estimatedSalary") or {}
    salary = salary if isinstance(salary, dict) else {}
    value = salary.get("value") or {}
    value = value if isinstance(value, dict) else {"value": value}
    identifier = item.get("identifier")
    if isinstance(identifier, dict):
        identifier = identifier.get("value")
    organization = item.get("hiringOrganization") or {}
    employment = item.get("employmentType")
    return {
        "id": identifier, "url": item.get("url") or page_url, "title": item.get("title"),
        "company": organization.get("name") if isinstance(organization, dict) else organization,
        "city": address.get("addressLocality"), "province": address.get("addressRegion"),
        "country_code": country, "description": item.get("description"), "skills": item.get("skills"),
        "salary_min": value.get("minValue", value.get("value")),
        "salary_max": value.get("maxValue", value.get("value")),
        "salary_currency": salary.get("currency", item.get("salaryCurrency")),
        "salary_period": str(value.get("unitText") or "").lower(),
        "salary_is_estimated": not bool(item.get("baseSalary")) and bool(item.get("estimatedSalary")),
        "employment_type": ", ".join(employment) if isinstance(employment, list) else employment,
        "work_mode": "remote" if item.get("jobLocationType") == "TELECOMMUTE" else None,
        "published_at": item.get("datePosted"), "expires_at": item.get("validThrough"),
        "education": item.get("educationRequirements") if isinstance(item.get("educationRequirements"), str) else None,
    }


def extract_jsonld(source, client, raw_dir):
    if source.get("approved") is not True:
        raise SourceError("JSON-LD source requires operator approved=true")
    records = []
    if not source.get("urls"):
        raise SourceError("JSON-LD source needs explicit approved detail-page URLs")
    for index, url in enumerate(source["urls"]):
        client.allow_page(url)
        body = client.get(url, "text/html")
        (raw_dir / f"page-{index + 1}.html").write_text(body, encoding="utf-8")
        parser = JsonLdParser()
        parser.feed(body)
        items = list(postings(parser.documents))
        if not items:
            raise SourceError("Configured detail page contains no schema.org JobPosting")
        records.extend(schema_record(item, url) for item in items)
    return records, {"configured_pages": len(source["urls"]), "bounded_search": True, "truncated": False}


def extract_rss(source, client, raw_dir):
    if source.get("approved") is not True or source.get("country_code") != "NL":
        raise SourceError("RSS source requires approved=true and country_code=NL")
    body = client.get(source["url"], "application/rss+xml, application/atom+xml, application/xml")
    (raw_dir / "feed.xml").write_text(body, encoding="utf-8")
    root = ET.fromstring(body)
    records = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: child for child in item}
        def field(*names, _fields=fields):
            for name in names:
                if name in _fields:
                    return "".join(_fields[name].itertext())
            return None
        link = field("link")
        if "link" in fields:
            link = fields["link"].get("href") or link
        records.append({"id": field("guid", "id") or link, "url": link, "title": field("title"),
                        "description": field("description", "summary", "content"),
                        "published_at": field("pubDate", "published", "updated"),
                        "country_code": "NL", "company": field("company"),
                        "city": field("location"), "province": None})
    return records, {"feed_entries": len(records), "bounded_search": True, "truncated": False}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def demo_records(snapshot_date):
    day = date.fromisoformat(snapshot_date)
    fixtures = json.loads((ROOT / "fixtures" / "jobs.json").read_text())
    rows = []
    for index, template in enumerate(fixtures):
        # Calendar-based deterministic cohorts: new observations and changing mix,
        # with no implication that a vacancy absent tomorrow has closed.
        if (day.toordinal() + index) % 11 == 0:
            continue
        record = dict(template)
        cohort_start = day.replace(day=1)
        record["published_at"] = (cohort_start - timedelta(days=(index % 10) + 1)).isoformat()
        record["expires_at"] = (cohort_start + timedelta(days=45 + index % 14)).isoformat()
        record["country_code"] = "NL"
        record["id"] = f"demo-{index + 1:03d}"
        record["url"] = f"https://{record['source']}.example/vacatures/{index + 1:03d}"
        rows.append(record)
        if index % 5 == 0:
            duplicate = dict(record, source="demo-techboard", id=f"repost-{index + 1:03d}",
                             url=f"https://demo-techboard.example/jobs/{index + 1:03d}")
            rows.append(duplicate)
    return rows


def run_snapshot(mode, snapshot_date, output_dir, config, client=None):
    """Stage a complete snapshot, then publish its date partition.

    Failed attempts are saved separately and never replace a successful partition.
    Same-date successful reruns replace the partition and SQLite rows, avoiding
    duplicate observations. Live observation time always reflects actual extraction.
    """
    date.fromisoformat(snapshot_date)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("snapshot_date=*/manifest.json"):
        if json.loads(existing.read_text()).get("mode") != mode:
            raise SourceError("Use separate output directories for demo and live data")
    stage = Path(tempfile.mkdtemp(prefix=".extract-", dir=output_dir))
    observed_at = snapshot_date + "T05:00:00Z" if mode == "demo" else datetime.now(UTC).isoformat().replace("+00:00", "Z")
    manifest = {"use_case": "dutch-it-jobs", "mode": mode, "snapshot_date": snapshot_date,
                "observed_at": observed_at, "is_synthetic": mode == "demo",
                "taxonomy_version": TAXONOMY_VERSION, "snapshot_timezone": "Europe/Amsterdam",
                "status": "running", "sources": [], "observation_count": 0,
                "coverage_note": "Bounded observations, not all Dutch vacancies. Absence never implies closure."}
    observations = {}
    failed = False
    sources = [{"name": "synthetic-fixtures", "adapter": "demo"}] if mode == "demo" else [s for s in config.get("sources", []) if s.get("enabled")]
    if not sources:
        shutil.rmtree(stage)
        raise SourceError("No enabled live sources; refusing to substitute synthetic data")
    adapters = {"adzuna": extract_adzuna, "jsonld": extract_jsonld, "rss": extract_rss}
    client = client or HttpClient(config)
    for source in sources:
        name = source["name"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            shutil.rmtree(stage)
            raise SourceError("Source names may contain only letters, numbers, underscore and hyphen")
        raw_dir = stage / "raw" / name
        raw_dir.mkdir(parents=True)
        os.chmod(raw_dir, 0o700)
        try:
            if mode == "demo":
                records = demo_records(snapshot_date)
                write_json(raw_dir / "jobs.json", records)
                details = {"bounded_search": True, "truncated": False}
            else:
                if source.get("adapter") not in adapters:
                    raise SourceError("Unknown source adapter")
                records, details = adapters[source["adapter"]](source, client, raw_dir)
            accepted = 0
            for record in records:
                row = normalize(record, record.get("source", name) if mode == "demo" else name,
                                snapshot_date, observed_at, mode == "demo")
                if row:
                    observations[row["job_id"]] = row
                    accepted += 1
            manifest["sources"].append({"source": name, "status": "success", "received": len(records), "accepted": accepted, **details})
        except (SourceError, ValueError, KeyError, TypeError, ET.ParseError) as error:
            failed = True
            # Parse errors may contain payload fragments; only explicit SourceError
            # messages are safe to persist. Network client already sanitizes URLs.
            message = str(error) if isinstance(error, SourceError) else f"Invalid source payload ({type(error).__name__})"
            manifest["sources"].append({"source": name, "status": "failed", "error": message})
        for raw_file in raw_dir.iterdir():
            os.chmod(raw_file, 0o600)
    normalized_dir = stage / "normalized"
    normalized_dir.mkdir()
    rows = sorted(observations.values(), key=lambda row: row["job_id"])
    (normalized_dir / "observations.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    manifest["status"] = "failed" if failed else "success"
    manifest["observation_count"] = len(rows)
    manifest["truncated"] = any(s.get("truncated", False) for s in manifest["sources"])
    write_json(stage / "manifest.json", manifest)
    partition = output_dir / ("failed" if failed else "") / f"snapshot_date={snapshot_date}"
    partition.parent.mkdir(parents=True, exist_ok=True)
    backup = partition.with_name("." + partition.name + ".previous")
    if backup.exists():
        if partition.exists():
            shutil.rmtree(backup)
        else:
            backup.rename(partition)
    if partition.exists():
        partition.rename(backup)
    try:
        stage.rename(partition)
    except OSError:
        if backup.exists():
            backup.rename(partition)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    if failed:
        raise SourceError(f"Extraction failed; see {partition / 'manifest.json'}. Successful snapshots were preserved.")
    return manifest


def deduplicate(rows):
    """One representative per date/group; keep all source rows in observations."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["snapshot_date"], row["duplicate_group_id"])].append(row)
    result = []
    for group in groups.values():
        # Prefer more complete evidence, then stable source id for deterministic ties.
        def rank(row):
            has_salary = row["salary_min"] is not None or row["salary_max"] is not None
            salary_rank = (1 if row["salary_is_estimated"] else 2) if has_salary else 0
            return salary_rank, sum(v is not None and v != [] for v in row.values()), row["job_id"]
        chosen = max(group, key=rank)
        chosen = dict(chosen)
        chosen["sources"] = sorted({r["source"] for r in group})
        chosen["source_observations"] = len(group)
        # Keep classification evidence from all reposts.
        chosen["domains"] = sorted({d for r in group for d in r["domains"]})
        chosen["skills"] = sorted({s for r in group for s in r["skills"]})
        result.append(chosen)
    return sorted(result, key=lambda r: (r["snapshot_date"], r["duplicate_group_id"]))


def build_analytics(output_dir):
    output_dir = Path(output_dir)
    rows = []
    manifests = []
    for partition in sorted(output_dir.glob("snapshot_date=*")):
        manifest = json.loads((partition / "manifest.json").read_text())
        if manifest.get("status") != "success":
            continue
        manifests.append(manifest)
        rows.extend(json.loads(line) for line in (partition / "normalized" / "observations.jsonl").read_text().splitlines())
    if not manifests:
        raise SourceError("No successful snapshots to analyze")
    deduped = deduplicate(rows)
    latest_date = max(m["snapshot_date"] for m in manifests)
    latest = [r for r in deduped if r["snapshot_date"] == latest_date]
    latest_source_rows = [r for r in rows if r["snapshot_date"] == latest_date]
    previous_dates = sorted({r["snapshot_date"] for r in deduped if r["snapshot_date"] < latest_date})
    previous_groups = {r["duplicate_group_id"] for r in deduped if previous_dates and r["snapshot_date"] == previous_dates[-1]}
    def counts(values):
        return [{"name": key, "count": value} for key, value in Counter(values).most_common()]
    domain_summary = []
    for domain in DOMAINS:
        jobs = [r for r in latest if domain in r["domains"]]
        salaries = [(r["salary_year_min"] + r["salary_year_max"]) / 2 for r in jobs if r["salary_year_min"] is not None and r["salary_year_max"] is not None and not r["salary_is_estimated"]]
        domain_summary.append({"domain": domain, "jobs": len(jobs),
                               "published_salary_jobs": len(salaries),
                               "avg_salary_eur_year": round(sum(salaries) / len(salaries)) if salaries else None,
                               "hybrid_remote_jobs": sum(r["work_mode"] in ("hybrid", "remote") for r in jobs)})
    dashboard = {
        "use_case": "dutch-it-jobs", "snapshot_date": latest_date,
        "is_synthetic": all(r["is_synthetic"] for r in latest_source_rows),
        "coverage_note": "Observed listings from configured sources. Domains overlap; salary averages exclude estimates, hourly rates and missing salary. Missing listings are never marked closed.",
        "summary": {"jobs": len(latest), "source_observations": len(latest_source_rows),
                    "duplicate_observations": len(latest_source_rows) - len(latest),
                    "sources": len({r["source"] for r in latest_source_rows}),
                    "companies": len({r["company"] for r in latest if r["company"]}),
                    "newly_observed_since_previous_snapshot": sum(r["duplicate_group_id"] not in previous_groups for r in latest) if previous_dates else None},
        "domains": domain_summary,
        "daily_trend": [{"snapshot_date": d, "jobs": sum(r["snapshot_date"] == d for r in deduped),
                         "source_observations": sum(r["snapshot_date"] == d for r in rows)} for d in sorted({m["snapshot_date"] for m in manifests})],
        "skills": counts(s for r in latest for s in r["skills"]),
        "locations": counts(r["city"] or "Unknown" for r in latest),
        "work_modes": counts(r["work_mode"] or "Unknown" for r in latest),
        "seniority": counts(r["seniority"] or "Unknown" for r in latest),
        "contracts": counts(r["contract_type"] or "Unknown" for r in latest),
        "quality": {"missing_salary": sum(r["salary_min"] is None for r in latest),
                    "estimated_salary": sum(r["salary_is_estimated"] for r in latest),
                    "hourly_salary": sum(r["salary_period"] == "hour" for r in latest),
                    "missing_location": sum(not r["city"] for r in latest),
                    "missing_company": sum(not r["company"] for r in latest),
                    "truncated_sources": sum(s.get("truncated", False) for m in manifests if m["snapshot_date"] == latest_date for s in m["sources"])},
        "listings": latest, "sources": [s for m in manifests if m["snapshot_date"] == latest_date for s in m["sources"]],
    }
    write_json(output_dir / "dashboard.json", dashboard)
    with closing(sqlite3.connect(output_dir / "job_market.sqlite")) as connection, connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots(snapshot_date TEXT PRIMARY KEY, mode TEXT, observation_count INTEGER, truncated INTEGER);
            CREATE TABLE IF NOT EXISTS observations(snapshot_date TEXT, job_id TEXT, duplicate_group_id TEXT, source TEXT, title TEXT, company TEXT, city TEXT, payload TEXT, PRIMARY KEY(snapshot_date,job_id));
            CREATE TABLE IF NOT EXISTS vacancies(snapshot_date TEXT, duplicate_group_id TEXT, title TEXT, company TEXT, city TEXT, work_mode TEXT, salary_year_min REAL, salary_year_max REAL, salary_is_estimated INTEGER, domains TEXT, skills TEXT, payload TEXT, PRIMARY KEY(snapshot_date,duplicate_group_id));
            DELETE FROM snapshots; DELETE FROM observations; DELETE FROM vacancies;
        """)
        connection.executemany("INSERT INTO snapshots VALUES(?,?,?,?)", [(m["snapshot_date"], m["mode"], m["observation_count"], m["truncated"]) for m in manifests])
        connection.executemany("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)", [(r["snapshot_date"], r["job_id"], r["duplicate_group_id"], r["source"], r["title"], r["company"], r["city"], json.dumps(r)) for r in rows])
        connection.executemany("INSERT INTO vacancies VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [(r["snapshot_date"], r["duplicate_group_id"], r["title"], r["company"], r["city"], r["work_mode"], r["salary_year_min"], r["salary_year_max"], r["salary_is_estimated"], json.dumps(r["domains"]), json.dumps(r["skills"]), json.dumps(r)) for r in deduped])
        connection.executescript("""
            DROP VIEW IF EXISTS latest_jobs;
            CREATE VIEW latest_jobs AS SELECT * FROM vacancies WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM snapshots);
            DROP VIEW IF EXISTS daily_market;
            CREATE VIEW daily_market AS SELECT s.snapshot_date,COUNT(v.duplicate_group_id) AS jobs,COUNT(DISTINCT v.company) AS companies FROM snapshots s LEFT JOIN vacancies v USING(snapshot_date) GROUP BY s.snapshot_date;
        """)
    return dashboard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("demo", "live"), default="demo")
    parser.add_argument("--date", default=snapshot_today().isoformat(), help="Europe/Amsterdam snapshot date; demo ends on this date")
    parser.add_argument("--days", type=int, default=7, help="Synthetic history days (demo only)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    parser.add_argument("--sources", type=Path, default=ROOT / "sources.json")
    args = parser.parse_args(argv)
    try:
        end = date.fromisoformat(args.date)
        if not 1 <= args.days <= 366:
            raise SourceError("--days must be between 1 and 366")
        if args.mode == "live" and end != snapshot_today():
            raise SourceError("Live extraction can only observe today's Europe/Amsterdam date; past dates require archived source payloads")
        config = json.loads(args.sources.read_text())
        days = args.days if args.mode == "demo" else 1
        for offset in range(days - 1, -1, -1):
            manifest = run_snapshot(args.mode, (end - timedelta(days=offset)).isoformat(), args.output_dir, config)
            print(f"{manifest['snapshot_date']}: {manifest['observation_count']} {args.mode} source observations")
        dashboard = build_analytics(args.output_dir)
        print(f"Latest: {dashboard['summary']['jobs']} deduplicated jobs; {args.output_dir / 'dashboard.json'}")
        return 0
    except (SourceError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
