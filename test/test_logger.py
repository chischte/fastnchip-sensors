import importlib.util
import sqlite3
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

    def test_scd_temperature_does_not_replace_pt100(self):
        logger.insert(self.db, {"boot_id": 12, "sequence": 1,
                               "boxtemp": 26.5, "scdtemp": 28.25,
                               "scd_offset": 4.0})
        stored = self.db.execute(
            "SELECT temp_box_c,temp_scd_c,scd_temperature_offset_c FROM measurements"
        ).fetchone()
        self.assertEqual((26.5, 28.25, 4.0), stored)

    def test_sensor_identity_survives_a_swap(self):
        for sequence, serial in enumerate(("000000000001", "000000000002"), 1):
            logger.insert(self.db, {"boot_id": 12, "sequence": sequence,
                                   "scd_serial": serial})
        self.assertEqual(
            [("000000000001",), ("000000000002",)],
            self.db.execute("SELECT scd_serial FROM measurements ORDER BY sequence").fetchall())

    def test_rtd_configuration_recovery_is_recorded(self):
        diagnostics = dict(zip(logger.RTD_DIAGNOSTIC_COLUMNS,
                               (9000, 8978, 0, 17, 17, 17, 1)))
        logger.insert(self.db, {"boot_id": 13, "sequence": 1, **diagnostics})
        stored = self.db.execute(
            "SELECT " + ",".join(logger.RTD_DIAGNOSTIC_COLUMNS) + " FROM measurements"
        ).fetchone()
        self.assertEqual(tuple(diagnostics.values()), stored)

    def test_migrate_existing_database_preserves_old_rows(self):
        path = Path(self.temp.name) / "legacy.db"
        with sqlite3.connect(path) as legacy:
            legacy.executescript(logger.SCHEMA)
            legacy.execute("""INSERT INTO measurements
                (received_at,boot_id,sequence,uptime_ms,temp_box_c,
                 valid_co2,valid_box,valid_humidity,valid_outer)
                VALUES ('2026-09-08',1,1,5000,25.5,0,1,0,0)""")
        legacy.close()
        for _ in range(2):
            migrated = logger.connect(path)
            try:
                stored = migrated.execute(
                    "SELECT temp_box_c,temp_scd_c,scd_temperature_offset_c FROM measurements"
                ).fetchone()
                self.assertEqual((25.5, None, None), stored)
            finally:
                migrated.close()
if __name__ == "__main__":
    unittest.main()
