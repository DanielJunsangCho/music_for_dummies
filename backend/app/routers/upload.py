"""PDF upload. Analysis starts here, in the background, exactly once."""

import os
import uuid

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services import jobs, pipeline

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
MAX_BYTES = 50 * 1024 * 1024


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    upload_id = str(uuid.uuid4())
    folder = os.path.join(UPLOAD_DIR, upload_id)
    os.makedirs(folder, exist_ok=True)

    pdf_path = os.path.join(folder, "original.pdf")
    async with aiofiles.open(pdf_path, 'wb') as handle:
        await handle.write(content)

    try:
        total = pipeline.page_count(pdf_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}") from exc

    def work(job):
        pipeline.analyze_upload(upload_id, pdf_path, job=job)

    jobs.submit(upload_id, work)

    return {
        "id": upload_id,
        "filename": file.filename,
        "pages": total,
        "status": "processing",
    }
