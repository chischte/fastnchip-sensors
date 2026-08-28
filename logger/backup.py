"""
fastnchip-sensors – daily backup
Creates a consistent dated backup of measurements.db.
Run daily via Windows Task Scheduler.
"""

import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
SOURCE = DATA_DIR / "measurements.db"
DEST = Path(r"G:\My Drive\AUTO_BKP_MESSDATEN\FASTNCHIP")
LOG  = Path(__file__).parent / "data" / "backup.log"


def notify(title: str, msg: str) -> None:
    """Show a Windows desktop toast notification via PowerShell."""
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f"$n.ShowBalloonTip(6000, '{title}', '{msg}', "
        "[System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Seconds 7; "
        "$n.Dispose()"
    )
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
        creationflags=0x08000000,   # CREATE_NO_WINDOW
    )


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def main() -> None:
    if not SOURCE.exists():
        log("SKIP: no measurement database found.")
        return

    drive = Path(DEST.anchor)
    if not drive.exists():
        msg = f"Drive '{drive}' not available — backup skipped."
        log(f"SKIP: {msg}")
        notify("Sensor Backup Skipped", msg)
        sys.exit(0)

    try:
        DEST.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        dest_file = DEST / f"measurements_{date_str}.db"
        with sqlite3.connect(SOURCE) as src_db, sqlite3.connect(dest_file) as dest_db:
            src_db.backup(dest_db)
        log(f"OK: Backed up {dest_file.name}")
        notify("Sensor Backup OK", f"Saved {dest_file.name} to Google Drive.")
    except Exception as exc:
        log(f"ERROR: {exc}")
        notify("Sensor Backup FAILED", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
