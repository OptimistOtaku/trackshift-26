"""Exercise the browser's actual evidence contracts, not a second implementation."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class JuryEvidenceTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for browser contracts')
    def test_browser_evidence_contracts(self):
        result = subprocess.run([shutil.which('node'), '--test', 'tests/test_evidence.js', 'tests/test_strategy_engine.js', 'tests/test_clock_ui.js'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
