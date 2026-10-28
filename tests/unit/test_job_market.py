"""Behavioral checks for the Dutch IT jobs reference use case (no network)."""
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

MODULE = Path(__file__).resolve().parents[2] / "examples/dutch-it-jobs/job_market.py"
spec = importlib.util.spec_from_file_location("job_market", MODULE)
jobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jobs)


class JobMarketTests(unittest.TestCase):
    def setUp(self):
        self.record = {"id": "42", "title": "Senior Data Engineer", "company": "Delta Data BV",
                       "city": "Amsterdam", "country_code": "NL", "url": "https://jobs.example/42?utm_source=mail#top",
                       "description": "Python, SQL, Spark en dbt. Hybride, HBO. Nederlands vereist.",
                       "salary_min": 5000, "salary_max": 7000, "salary_period": "month", "salary_currency": "EUR"}

    def normalize(self, **changes):
        return jobs.normalize(dict(self.record, **changes), "board-a", "2026-10-28", "2026-10-28T05:00:00Z")

    def test_normalization_preserves_evidence_and_monthly_salary(self):
        row = self.normalize()
        self.assertEqual(row["salary_year_min"], 60000)
        self.assertEqual(row["salary_year_max"], 84000)
        self.assertEqual(row["salary_period"], "month")
        self.assertEqual(row["work_mode"], "hybrid")
        self.assertEqual(row["seniority"], "senior")
        self.assertEqual(row["language"], "Dutch required")
        self.assertEqual(row["canonical_url"], "https://jobs.example/42")
        self.assertEqual(row["domains"], ["data"])
        self.assertIsNone(row["published_at"])
        self.assertFalse(row["is_synthetic"])

    def test_salary_unknown_hourly_non_eur_and_invalid_ranges(self):
        for changes in [{"salary_period": "hour"}, {"salary_currency": "USD"},
                        {"salary_period": None}, {"salary_min": None},
                        {"salary_min": 9000, "salary_max": 8000}]:
            self.assertIsNone(self.normalize(**changes)["salary_year_min"])
        self.assertTrue(self.normalize(salary_is_estimated="1")["salary_is_estimated"])

    def test_contact_redaction_and_boundary_classification(self):
        row = self.normalize(description="Email eva@company.nl or call 06-12345678 and +31 20 1234567. Python SQL.")
        self.assertNotIn("eva@", row["description_text"])
        self.assertNotIn("12345678", row["description_text"])
        self.assertNotIn("1234567", row["description_text"])
        self.assertEqual(self.normalize(title="JavaScript Developer", description="JavaScript, React")["skills"], ["JavaScript", "React"])
        self.assertNotIn("ai", self.normalize(description="Maintaining a retail data platform")["domains"])

    def test_no_non_it_or_non_nl_or_titleless_observations(self):
        self.assertIsNone(self.normalize(title="Accountant", description="Finance administration"))
        self.assertIsNone(self.normalize(country_code="DE"))
        self.assertIsNone(self.normalize(country_code=None))
        self.assertIsNone(self.normalize(title=""))
        self.assertIsNone(self.normalize(url=None))
        self.assertIsNone(self.normalize(url="javascript:bad"))

    def test_dutch_domain_titles_and_punctuated_languages(self):
        cases = {".NET Engineer": "software", "C# Engineer": "software",
                 "Data-analist": "data", "Data analist": "data",
                 "Data engineer": "data", "Data architect": "data",
                 "Programmeur": "software", "Expert kunstmatige intelligentie": "ai"}
        for title, domain in cases.items():
            with self.subTest(title=title):
                row = self.normalize(title=title, description="")
                self.assertIsNotNone(row)
                self.assertIn(domain, row["domains"])
        for title in ("Administrateur", "Dataverwerker", "Metadata coordinator", "C#sharpener", ".network planner"):
            with self.subTest(non_it_title=title):
                self.assertIsNone(self.normalize(title=title, description=""))

    def test_multilabel_and_conservative_cross_board_dedup(self):
        row = self.normalize(title="SAP Cloud Security Engineer", description="SAP Azure IAM")
        self.assertEqual(row["domains"], ["cloud", "sap", "security"])
        repost = jobs.normalize(self.record, "board-b", "2026-10-28", "2026-10-28T05:00:00Z")
        original = self.normalize()
        deduped = jobs.deduplicate([original, repost])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["sources"], ["board-a", "board-b"])
        self.assertNotEqual(original["job_id"], repost["job_id"])
        unknown_a = jobs.normalize(dict(self.record, company=None), "board-a", "2026-10-28", "now")
        unknown_b = jobs.normalize(dict(self.record, company=None), "board-b", "2026-10-28", "now")
        self.assertEqual(len(jobs.deduplicate([unknown_a, unknown_b])), 2)

    def test_dedup_prefers_reported_salary_and_preserves_classification_evidence(self):
        original = self.normalize(salary_is_estimated=True, description="Python Azure data engineer")
        reported = jobs.normalize(self.record, "board-b", "2026-10-28", "now")
        result = jobs.deduplicate([original, reported])[0]
        self.assertEqual(result["job_id"], reported["job_id"])
        self.assertFalse(result["salary_is_estimated"])
        self.assertIn("cloud", result["domains"])
        self.assertIn("Azure", result["skills"])

    def test_dedup_keeps_estimate_when_other_repost_has_no_salary(self):
        estimated = self.normalize(salary_is_estimated=True)
        missing = jobs.normalize(dict(self.record, salary_min=None, salary_max=None), "board-b", "2026-10-28", "now")
        result = jobs.deduplicate([estimated, missing])[0]
        self.assertEqual(result["job_id"], estimated["job_id"])
        self.assertTrue(result["salary_is_estimated"])
        self.assertEqual(result["salary_min"], 5000)

    def test_snapshot_today_uses_amsterdam_and_live_rejects_other_dates(self):
        with patch.object(jobs, "datetime") as clock:
            clock.now.return_value.date.return_value = date(2026, 10, 29)
            self.assertEqual(jobs.snapshot_today(), date(2026, 10, 29))
            clock.now.assert_called_once_with(jobs.SNAPSHOT_TIMEZONE)
        with patch.object(jobs, "snapshot_today", return_value=date(2026, 10, 29)), patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(jobs.main(["--mode", "live", "--date", "2026-10-28"]), 1)

    def test_schema_org_salary_date_and_multiple_types(self):
        item = {"@type": ["Thing", "JobPosting"], "title": "SAP Consultant", "identifier": {"value": "x"},
                "hiringOrganization": {"name": "Demo"}, "jobLocation": {"address": {"addressCountry": "NL", "addressLocality": "Utrecht"}},
                "baseSalary": {"currency": "EUR", "value": {"minValue": 4000, "maxValue": 6000, "unitText": "MONTH"}},
                "datePosted": "2026-10-01", "validThrough": "2026-11-01"}
        self.assertEqual(list(jobs.postings({"@graph": [item]})), [item])
        record = jobs.schema_record(item, "https://careers.example/job")
        normalized = jobs.normalize(record, "demo", "2026-10-28", "now")
        self.assertEqual(normalized["salary_year_max"], 72000)
        self.assertEqual(normalized["published_at"], "2026-10-01T00:00:00Z")

    def test_demo_is_idempotent_and_sqlite_matches_json(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs.run_snapshot("demo", "2026-10-28", directory, {})
            partition = Path(directory) / "snapshot_date=2026-10-28"
            before = (partition / "normalized/observations.jsonl").read_bytes()
            first = jobs.build_analytics(directory)
            jobs.run_snapshot("demo", "2026-10-28", directory, {})
            second = jobs.build_analytics(directory)
            self.assertEqual(before, (partition / "normalized/observations.jsonl").read_bytes())
            self.assertEqual(first, second)
            self.assertGreater(first["summary"]["duplicate_observations"], 0)
            self.assertEqual({row["domain"] for row in first["domains"]}, set(jobs.DOMAINS))
            self.assertTrue(all(row["jobs"] > 0 for row in first["domains"]))
            with closing(sqlite3.connect(Path(directory) / "job_market.sqlite")) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM latest_jobs").fetchone()[0], first["summary"]["jobs"])
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0], first["summary"]["source_observations"])
            mode = (partition / "raw/synthetic-fixtures/jobs.json").stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_failed_live_extraction_never_publishes_partial_or_fake_data(self):
        config = {"sources": [{"name": "adzuna-nl", "adapter": "adzuna", "enabled": True}]}
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(jobs.SourceError):
                jobs.run_snapshot("live", "2026-10-28", directory, config)
            self.assertFalse((Path(directory) / "snapshot_date=2026-10-28").exists())
            failure = json.loads((Path(directory) / "failed/snapshot_date=2026-10-28/manifest.json").read_text())
            self.assertEqual(failure["status"], "failed")
            self.assertFalse(failure["is_synthetic"])
            self.assertEqual(failure["observation_count"], 0)

    def test_output_directory_cannot_mix_live_and_synthetic(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs.run_snapshot("demo", "2026-10-28", directory, {})
            with self.assertRaisesRegex(jobs.SourceError, "separate output"):
                jobs.run_snapshot("live", "2026-10-29", directory, {})

    def test_retries_are_bounded_and_credentials_are_not_in_error(self):
        client = jobs.HttpClient({"retries": 2, "request_interval_seconds": 0})
        with patch.object(jobs, "urlopen", side_effect=URLError("https://api.example?app_key=SECRET")) as mocked, patch.object(jobs.time, "sleep"):
            with self.assertRaises(jobs.SourceError) as error:
                client.get("https://api.example?app_key=SECRET")
            self.assertEqual(mocked.call_count, 3)
            self.assertNotIn("SECRET", str(error.exception))
        denied = HTTPError("https://api.example?app_key=SECRET", 403, "denied", {}, io.BytesIO())
        with patch.object(jobs, "urlopen", side_effect=denied) as mocked, patch.object(jobs.time, "sleep"):
            with self.assertRaisesRegex(jobs.SourceError, "403"):
                client.get("https://api.example?app_key=SECRET")
            self.assertEqual(mocked.call_count, 1)

    def test_adzuna_pagination_marks_truncation_and_uses_nl(self):
        class Client:
            def __init__(self):
                self.urls = []
            def get(self, url):
                self.urls.append(url)
                return json.dumps({"count": 1000, "results": [{"id": "x", "title": "Data Engineer"}]})
        client = Client()
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"ADZUNA_APP_ID": "id", "ADZUNA_APP_KEY": "key"}):
            records, details = jobs.extract_adzuna({"queries": ["data"], "max_pages_per_query": 2, "results_per_page": 1}, client, Path(directory))
        self.assertEqual(len(records), 2)
        self.assertTrue(details["truncated"])
        self.assertTrue(all("/jobs/nl/search/" in url for url in client.urls))

    def test_robots_denial_blocks_page_fetch(self):
        client = jobs.HttpClient({})
        with patch.object(client, "get", return_value="User-agent: *\nDisallow: /jobs\n") as mocked:
            with self.assertRaisesRegex(jobs.SourceError, "robots"):
                client.allow_page("https://careers.example/jobs/42")
            self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
