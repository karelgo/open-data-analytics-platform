"""Optional real Airflow parse check; no network or cluster is contacted."""

import sys
import unittest
from pathlib import Path

AIRFLOW = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AIRFLOW / "include"))


class JobMarketDagIntegrity(unittest.TestCase):
    def test_dagbag_import(self):
        try:
            from airflow.models import DagBag
        except ImportError:
            self.skipTest(
                "Install Airflow 3 and the Kubernetes provider to validate DAG imports"
            )
        bag = DagBag(dag_folder=str(AIRFLOW / "dags"), include_examples=False)
        self.assertEqual(bag.import_errors, {})
        self.assertEqual(set(bag.dags), {"dutch_it_jobs_daily"})
        dag = bag.dags["dutch_it_jobs_daily"]
        self.assertFalse(dag.catchup)
        self.assertEqual(dag.max_active_runs, 1)
        self.assertEqual(dag.timezone.name, "Europe/Amsterdam")
        self.assertEqual(dag.get_task("transform").upstream_task_ids, {"bronze"})
        self.assertEqual(
            dag.get_task("publish_job_dashboard").upstream_task_ids,
            {"register_job_datasets"},
        )
