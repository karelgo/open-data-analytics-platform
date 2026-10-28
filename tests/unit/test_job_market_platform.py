"""Object-store publication must never expose failed or mixed-mode extracts."""

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "infrastructure/job-market/runtime.py"
spec = importlib.util.spec_from_file_location("job_market_platform", MODULE)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class MissingObject(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "NoSuchKey"}}


class MemoryStore:
    def __init__(self):
        self.objects = {}
        self.fail_upload = False

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise MissingObject()
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.objects[Key] = Body

    def upload_file(self, filename, bucket, key):
        if self.fail_upload:
            raise OSError("simulated interrupted upload")
        self.objects[key] = Path(filename).read_bytes()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / "normalized").mkdir()
        (self.directory / "normalized/observations.jsonl").write_text(
            '{"job_id":"a"}\n'
        )
        self.manifest = {
            "status": "success",
            "snapshot_date": "2026-10-28",
            "mode": "demo",
            "observation_count": 1,
        }
        self.write_manifest()
        self.store = MemoryStore()

    def write_manifest(self):
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))

    def publish(self):
        runtime.publish_extract(
            self.store, "bronze", self.directory, "2026-10-28", "demo"
        )

    def test_retry_switches_pointer_to_new_immutable_attempt(self):
        self.publish()
        key = "job-market/raw/snapshot_date=2026-10-28/current.json"
        first = json.loads(self.store.objects[key])
        self.publish()
        second = json.loads(self.store.objects[key])
        self.assertNotEqual(first["attempt_prefix"], second["attempt_prefix"])
        for pointer in [first, second]:
            self.assertIn(
                pointer["attempt_prefix"] + "/manifest.json", self.store.objects
            )
            self.assertIn(
                pointer["attempt_prefix"] + "/normalized/observations.jsonl",
                self.store.objects,
            )

    def test_failed_upload_preserves_previous_successful_pointer(self):
        self.publish()
        key = "job-market/raw/snapshot_date=2026-10-28/current.json"
        before = self.store.objects[key]
        self.store.fail_upload = True
        with self.assertRaises(OSError):
            self.publish()
        self.assertEqual(self.store.objects[key], before)

    def test_live_cannot_overwrite_demo_lakehouse(self):
        self.publish()
        with self.assertRaisesRegex(RuntimeError, "another data mode"):
            runtime.ensure_mode(self.store, "bronze", "live")
        self.assertEqual(
            json.loads(self.store.objects["job-market/mode.json"])["mode"], "demo"
        )

    def test_failed_empty_and_mismatched_manifests_never_publish(self):
        for update in [
            {"status": "failed"},
            {"observation_count": 0},
            {"snapshot_date": "2026-10-27"},
            {"mode": "live"},
        ]:
            with self.subTest(update=update):
                original = dict(self.manifest)
                self.manifest.update(update)
                self.write_manifest()
                with self.assertRaises(RuntimeError):
                    self.publish()
                self.assertEqual(self.store.objects, {})
                self.manifest = original
