"""
File purpose:
- Defines upload API endpoints.
- Handles file or URL ingestion and returns extracted text preview.
"""

from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import shutil
from app.ingestion.router import load_file, load_url
from app.config.settings import UPLOAD_DIR

router = APIRouter(tags=["ingestion"])
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_file(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
):
    if (file is None and not url) or (file is not None and url):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one input: either 'file' or 'url'.",
        )

    if url:
        try:
            text = load_url(url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "status": "success",
            "message": "URL load completed successfully",
            "source": "url",
            "text_preview": text[:500],
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    file_path = UPLOAD_DIR / Path(file.filename).name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        text = load_file(file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "success",
        "message": "Load completed successfully",
        "source": "file",
        "text_preview": text[:500],
    }
