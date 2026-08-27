"""
fastnchip-sensors logger
Polls the sensor web API every POLL_INTERVAL seconds and appends
measurements to a CSV file for long-term analysis.
"""

import csv
import sys
import time
import urllib.request
import json
from datetime import datetime
from pathlib import Path

SENSOR_URL = "http://192.168.31.168/api/measurement"
POLL_INTERVAL = 5          # seconds between polls
CSV_DIR = Path(__file__).parent / "data"
CSV_FILE = CSV_DIR / "measurements.csv"
CSV_HEADER = ["timestamp", "co2_ppm", "temp_box_c", "humidity_rh", "temp_outer_c"]


def fetch_measurement(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            return json.loads(response.read().decode())
    except Exception as exc:
        print(f"[{timestamp()}] fetch error: {exc}", file=sys.stderr)
        return None


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_row(row: list) -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not CSV_FILE.exists()
    with CSV_FILE.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_HEADER)
        writer.writerow(row)


def main() -> None:
    print(f"Logging to {CSV_FILE}")
    print(f"Polling {SENSOR_URL} every {POLL_INTERVAL}s — Ctrl+C to stop\n")

    last_co2 = None

    while True:
        data = fetch_measurement(SENSOR_URL)
        if data:
            co2  = data.get("co2")
            temp = data.get("boxtemp")
            hum  = data.get("humidity")
            rtd  = data.get("outertemp", "")
            if co2 == last_co2:
                time.sleep(POLL_INTERVAL)
                continue

            last_co2 = co2
            ts = timestamp()
            append_row([ts, co2, temp, hum, rtd])
            diff = f"  ΔT: +{temp - rtd:.1f}°C" if isinstance(rtd, (int, float)) and rtd else ""
            print(f"{ts}  CO2: {co2} ppm  Box: {temp}°C  Outer: {rtd}°C{diff}  Hum: {hum}%RH")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nLogger stopped.")
