"""Backup script — zips .env, config.json, and event_agent.db into backups/.

Usage:
    python scripts/backup.py             # creates backups/attendable_TIMESTAMP.zip
    python scripts/backup.py --auto      # creates backups/auto_update_TIMESTAMP.zip
"""
import sys
import zipfile
from datetime import datetime
from pathlib import Path

AUTO = "--auto" in sys.argv

# Resolve paths relative to repo root (script may be run from any CWD)
REPO_ROOT = Path(__file__).parent.parent
BACKUP_DIR = REPO_ROOT / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

FILES = [".env", "config.json", "event_agent.db"]
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
prefix = "auto_update_" if AUTO else "attendable_"
archive_path = BACKUP_DIR / f"{prefix}{ts}.zip"

included = []
with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for fname in FILES:
        fpath = REPO_ROOT / fname
        if fpath.exists():
            zf.write(fpath, fname)
            included.append(fname)

if included:
    print(f"Backup created: {archive_path}")
    print(f"  Included: {', '.join(included)}")
else:
    print("Nothing to back up (no .env, config.json, or event_agent.db found)")
