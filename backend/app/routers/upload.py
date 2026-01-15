"""
PDF upload endpoint.
"""

import os
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models import UploadResponse
from app.services.pdf_processor import process_pdf

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF sheet music file for analysis.

    Returns an ID that can be used to retrieve analysis results.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Validate file size (max 50MB)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    # Generate unique ID
    file_id = str(uuid.uuid4())

    # Create directory for this upload
    upload_path = os.path.join(UPLOAD_DIR, file_id)
    os.makedirs(upload_path, exist_ok=True)

    # Save the PDF
    pdf_path = os.path.join(upload_path, "original.pdf")
    async with aiofiles.open(pdf_path, 'wb') as f:
        await f.write(content)

    # Start PDF processing (converts pages to images)
    try:
        await process_pdf(file_id, pdf_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    return UploadResponse(
        id=file_id,
        filename=file.filename,
        status="processing",
        message="PDF uploaded successfully. Analysis starting."
    )
