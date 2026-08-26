"""
fastnchip-sensors – daily backup
Copies measurements.csv to the backup folder with today's date appended.
Run daily via Windows Task Scheduler.
"""

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SRC  = Path(__file__).parent / "data" / "measurements.csv"
DEST = Path(r"G:\My Drive\DELIA_ENGINEERING\MUSHCULT\CULTIVATION_LOG\fastnchip_data_backup")
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
    if not SRC.exists():
        log("SKIP: measurements.csv not found.")
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
        dest_file = DEST / f"measurements_{date_str}.csv"
        shutil.copy2(SRC, dest_file)
        log(f"OK: Backed up to {dest_file}")
        notify("Sensor Backup OK", f"Saved measurements_{date_str}.csv to Google Drive.")
    except Exception as exc:
        log(f"ERROR: {exc}")
        notify("Sensor Backup FAILED", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
