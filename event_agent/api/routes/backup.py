"""Backup / restore API routes."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from event_agent.config.settings import get_settings

router = APIRouter(prefix="/backup", tags=["backup"])

_SAFE_FILES = {".env", "config.json", "event_agent.db"}


@router.post("")
async def create_backup():
    """Download a zip archive of user data files."""
    buf = io.BytesIO()
    included = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in _SAFE_FILES:
            p = Path(fname)
            if p.exists():
                zf.write(p, fname)
                included.append(fname)

    if not included:
        raise HTTPException(404, "No data files found to back up")

    buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"attendable_backup_{ts}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/restore")
async def restore_backup(file: UploadFile):
    """Restore from a previously downloaded backup zip."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "Upload must be a .zip file")

    data = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid zip file")

    names_in_zip = set(zf.namelist())
    to_restore = names_in_zip & _SAFE_FILES
    if not to_restore:
        raise HTTPException(400, "Zip does not contain any recognised data files (.env, config.json, event_agent.db)")

    restored = []
    for fname in to_restore:
        content = zf.read(fname)
        Path(fname).write_bytes(content)
        restored.append(fname)

    # Invalidate settings cache if .env was restored
    if ".env" in restored:
        get_settings.cache_clear()

    return {"ok": True, "restored": sorted(restored)}
