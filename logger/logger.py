"""Reliable Portenta logger: QSPI backfill -> SQLite -> optional CSV export."""
import argparse
import csv
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
DB_FILE = BASE / "data" / "measurements.db"
CSV_FILE = BASE / "data" / "measurements.csv"
DEFAULT_URL = os.getenv("SENSOR_URL", "http://192.168.31.168")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "5"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements(
 id INTEGER PRIMARY KEY, received_at TEXT NOT NULL, device_time TEXT,
 boot_id INTEGER NOT NULL, sequence INTEGER NOT NULL, uptime_ms INTEGER NOT NULL,
 co2_ppm INTEGER, temp_box_c REAL, humidity_rh REAL, temp_outer_c REAL,
 valid_co2 INTEGER NOT NULL, valid_box INTEGER NOT NULL,
 valid_humidity INTEGER NOT NULL, valid_outer INTEGER NOT NULL,
 rtd_box_fault INTEGER NOT NULL DEFAULT 0, rtd_outer_fault INTEGER NOT NULL DEFAULT 0,
 UNIQUE(boot_id, sequence));
CREATE INDEX IF NOT EXISTS ix_measurements_received ON measurements(received_at);
"""

def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def connect(path: Path = DB_FILE) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.executescript(SCHEMA)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db

def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.load(response)

def fetch_backlog(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        for raw in response:
            try:
                yield json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

def normalize(payload: dict) -> dict:
    record = payload.get("measurement", payload)
    valid = record.get("valid", {})
    faults = record.get("faults", {})
    return {
        "received_at": now(), "device_time": None,
        "boot_id": int(record["boot_id"]), "sequence": int(record["sequence"]),
        "uptime_ms": int(record.get("uptime_ms", 0)),
        "co2_ppm": record.get("co2"), "temp_box_c": record.get("boxtemp"),
        "humidity_rh": record.get("humidity"), "temp_outer_c": record.get("outertemp"),
        "valid_co2": int(valid.get("co2", record.get("co2") is not None)),
        "valid_box": int(valid.get("boxtemp", record.get("boxtemp") is not None)),
        "valid_humidity": int(valid.get("humidity", record.get("humidity") is not None)),
        "valid_outer": int(valid.get("outertemp", record.get("outertemp") is not None)),
        "rtd_box_fault": int(faults.get("rtd_box", 0)),
        "rtd_outer_fault": int(faults.get("rtd_outer", 0)),
    }

FIELDS = tuple(normalize({"boot_id": 0, "sequence": 0}).keys())
def insert(db: sqlite3.Connection, payload: dict) -> bool:
    row = normalize(payload)
    sql = f"INSERT OR IGNORE INTO measurements({','.join(FIELDS)}) VALUES({','.join('?' for _ in FIELDS)})"
    before = db.total_changes
    db.execute(sql, tuple(row[key] for key in FIELDS))
    db.commit()
    return db.total_changes > before

def import_csv(db: sqlite3.Connection, path: Path = CSV_FILE) -> int:
    if not path.exists() or db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]:
        return 0
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as file:
        for sequence, row in enumerate(csv.DictReader(file), 1):
            payload = {"boot_id": 0, "sequence": sequence, "uptime_ms": sequence * 5000,
                       "co2": _number(row.get("co2_ppm")), "boxtemp": _number(row.get("temp_box_c")),
                       "humidity": _number(row.get("humidity_rh")), "outertemp": _number(row.get("temp_outer_c"))}
            if insert(db, payload):
                db.execute("UPDATE measurements SET received_at=?, device_time=? WHERE boot_id=0 AND sequence=?",
                           (row["timestamp"], row["timestamp"], sequence))
                count += 1
    db.commit()
    return count

def _number(value):
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None

def export_csv(db: sqlite3.Connection, path: Path = CSV_FILE) -> None:
    temp = path.with_suffix(".csv.tmp")
    with temp.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "co2_ppm", "temp_box_c", "humidity_rh", "temp_outer_c",
                         "boot_id", "sequence", "valid_co2", "valid_box", "valid_humidity", "valid_outer"])
        writer.writerows(db.execute("""SELECT COALESCE(device_time,received_at),co2_ppm,temp_box_c,humidity_rh,temp_outer_c,
            boot_id,sequence,valid_co2,valid_box,valid_humidity,valid_outer FROM measurements ORDER BY id"""))
    temp.replace(path)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--export-csv", action="store_true")
    args = parser.parse_args()
    with connect() as db:
        imported = import_csv(db)
        if imported: print(f"Imported {imported} existing CSV rows.")
        if args.export_csv:
            export_csv(db); print(f"Exported {CSV_FILE}"); return
        try:
            recovered = sum(insert(db, row) for row in fetch_backlog(args.url + "/api/backlog"))
            print(f"Recovered {recovered} buffered rows from Portenta.")
        except Exception as exc:
            print(f"Backfill unavailable: {exc}", file=sys.stderr)
        print(f"Logging {args.url} to {DB_FILE}")
        last_export = time.monotonic()
        while True:
            started = time.monotonic()
            try:
                payload = fetch_json(args.url + "/api/measurement")
                if insert(db, payload):
                    row = normalize(payload)
                    print(f"{row['received_at']}  #{row['sequence']}  CO2={row['co2_ppm']}  "
                          f"Box={row['temp_box_c']} C  Outer={row['temp_outer_c']} C  RH={row['humidity_rh']}%")
            except Exception as exc:
                print(f"[{now()}] fetch error: {exc}", file=sys.stderr)
            if time.monotonic() - last_export >= 3600:
                export_csv(db); last_export = time.monotonic()
            time.sleep(max(0, POLL_INTERVAL - (time.monotonic() - started)))

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nLogger stopped.")
