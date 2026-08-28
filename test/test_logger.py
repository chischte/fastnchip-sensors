import importlib.util
import tempfile
import unittest
from pathlib import Path
SPEC = importlib.util.spec_from_file_location("sensor_logger", Path(__file__).parents[1] / "logger" / "logger.py")
logger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(logger)
class LoggerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = logger.connect(Path(self.temp.name) / "test.db")
    def tearDown(self):
        self.db.close(); self.temp.cleanup()
    def test_sequence_deduplication(self):
        row = {"boot_id": 7, "sequence": 1, "uptime_ms": 5000, "co2": 900,
               "boxtemp": 24.0, "humidity": 80.0, "outertemp": 20.0}
        self.assertTrue(logger.insert(self.db, row))
        self.assertFalse(logger.insert(self.db, row))
        self.assertTrue(logger.insert(self.db, {**row, "sequence": 2, "humidity": 81.0}))
        self.assertEqual(2, self.db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0])
    def test_invalid_values_stay_null(self):
        row = {"boot_id": 1, "sequence": 1, "uptime_ms": 5, "co2": None,
               "boxtemp": None, "humidity": None, "outertemp": 20,
               "valid": {"co2": False, "boxtemp": False, "humidity": False, "outertemp": True},
               "faults": {"rtd_box": 4}}
        logger.insert(self.db, row)
        stored = self.db.execute("SELECT co2_ppm,temp_box_c,valid_co2,rtd_box_fault FROM measurements").fetchone()
        self.assertEqual((None, None, 0, 4), stored)
if __name__ == "__main__":
    unittest.main()
