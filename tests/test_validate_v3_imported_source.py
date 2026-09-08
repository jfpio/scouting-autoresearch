import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_v3_imported_source import imported_source_errors


class ValidateV3ImportedSourceTests(unittest.TestCase):
    def test_completed_zwolakowska_source_passes(self):
        self.assertEqual(imported_source_errors("zwolakowska-cub-pack-1945"), [])


if __name__ == "__main__":
    unittest.main()
