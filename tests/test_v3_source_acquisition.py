import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from acquire_v3_sources import AcquisitionError, load_plan, polona_image_url


class V3SourceAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = "/tmp/scouting-autoresearch-test-scratch"

    def test_approved_polona_source_is_scratch_only(self):
        with patch.dict(os.environ, {"SCRATCH": self.scratch}):
            plan = load_plan("jasinski-field-games-1938")
        self.assertEqual(plan.collection_id, "polona")
        self.assertEqual(plan.method, "polona-uuid-record")
        self.assertEqual(plan.expected_host, "polona.pl")
        self.assertTrue(str(plan.source_directory).startswith(self.scratch))

    def test_approved_direct_pdf_is_pinned_to_registered_host(self):
        with patch.dict(os.environ, {"SCRATCH": self.scratch}):
            plan = load_plan("piasecki-movement-games-1922")
        self.assertEqual(plan.expected_host, "kpbc.umk.pl")
        self.assertTrue(plan.artifact_url.startswith("https://kpbc.umk.pl/Content/"))

    def test_robots_blocked_zip_never_builds_an_execution_plan(self):
        with patch.dict(os.environ, {"SCRATCH": self.scratch}):
            with self.assertRaisesRegex(AcquisitionError, "blocked-by-robots"):
                load_plan("dabrowski-winter-games-1935")

    def test_polona_image_url_accepts_only_pinned_https_iiif_shape(self):
        self.assertEqual(
            polona_image_url("https://polona.pl/iiif/3/abc/info.json"),
            "https://polona.pl/iiif/3/abc/full/1600,/0/default.jpg",
        )
        with self.assertRaises(AcquisitionError):
            polona_image_url("https://example.test/iiif/3/abc/info.json")

    def test_slurm_job_records_explicit_cpu_resources_and_scratch_logs(self):
        job = (
            Path(__file__).resolve().parents[1]
            / "jobs"
            / "helios"
            / "v3-acquire-source.slurm"
        ).read_text(encoding="utf-8")
        self.assertTrue(job.startswith("#!/bin/bash -l\n"))
        self.assertIn("#SBATCH --partition=plgrid", job)
        self.assertIn("#SBATCH --account=plgcredibleai2026-cpu", job)
        self.assertIn("#SBATCH --cpus-per-task=1", job)
        self.assertIn("#SBATCH --mem=2G", job)
        self.assertIn("/plgrid/%u/scouting-autoresearch/logs/", job)
        self.assertNotIn("plgjfpio", job)

    def test_contact_sheet_job_is_small_cpu_work_in_scratch(self):
        job = (
            Path(__file__).resolve().parents[1]
            / "jobs"
            / "helios"
            / "v3-polona-contact-sheet.slurm"
        ).read_text(encoding="utf-8")
        self.assertIn("#SBATCH --account=plgcredibleai2026-cpu", job)
        self.assertIn("#SBATCH --cpus-per-task=1", job)
        self.assertIn("#SBATCH --mem=2G", job)
        self.assertIn('${SCRATCH}/scouting-autoresearch/runs/${SOURCE_ID}', job)
        self.assertIn("ImageMagick/7.1.2-7", job)


if __name__ == "__main__":
    unittest.main()
