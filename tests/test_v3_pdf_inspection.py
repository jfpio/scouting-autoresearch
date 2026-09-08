import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from inspect_v3_pdf import parse_pdfinfo, text_classification


class V3PdfInspectionTests(unittest.TestCase):
    def test_pdfinfo_parser_keeps_only_safe_operational_fields(self):
        parsed = parse_pdfinfo(
            "Title: untrusted title\nPages: 226\nPage size: 595 x 842 pts\n"
            "Encrypted: no\nTagged: no\nPDF version: 1.5\n"
        )
        self.assertEqual(parsed["pages"], 226)
        self.assertNotIn("Title", parsed)
        self.assertEqual(parsed["pdfVersion"], "1.5")

    def test_text_classification_requires_nontrivial_coverage(self):
        self.assertEqual(text_classification("abc " * 1000, 20), "embedded-text-available")
        self.assertEqual(text_classification("abc", 200), "image-ocr-required")

    def test_slurm_job_uses_verified_cpu_stack(self):
        job = (
            Path(__file__).resolve().parents[1]
            / "jobs"
            / "helios"
            / "v3-inspect-pdf.slurm"
        ).read_text(encoding="utf-8")
        self.assertIn("#SBATCH --account=plgcredibleai2026-cpu", job)
        self.assertIn("poppler/25.12.0", job)
        self.assertIn("#SBATCH --cpus-per-task=1", job)
        self.assertIn("#SBATCH --mem=2G", job)
        self.assertNotIn("plgjfpio", job)


if __name__ == "__main__":
    unittest.main()
