"""
Analysis results.

These endpoints are strictly read-only. Fetching a result never kicks off
analysis; if a job was never started for an id the caller is told so.
"""

import os

from fastapi import APIRouter, HTTPException

from app.services import jobs, pipeline

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


@router.get("/analysis/{upload_id}")
async def get_analysis(upload_id: str):
    job = jobs.get_job(upload_id)
    if job is not None:
        return job.snapshot()

    cached = jobs.load_cached(upload_id, pipeline.cached_result_path(upload_id))
    if cached is not None:
        return cached.snapshot()

    folder = os.path.join(UPLOAD_DIR, upload_id)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Unknown upload id")

    pdf_path = os.path.join(folder, "original.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Upload has no PDF")

    # The PDF survived a restart but the job did not; start it again once.
    def work(job):
        pipeline.analyze_upload(upload_id, pdf_path, job=job)

    return jobs.submit(upload_id, work).snapshot()


@router.post("/analysis/{upload_id}/reanalyze")
async def reanalyze(upload_id: str):
    folder = os.path.join(UPLOAD_DIR, upload_id)
    pdf_path = os.path.join(folder, "original.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Unknown upload id")

    cached = pipeline.cached_result_path(upload_id)
    if os.path.exists(cached):
        os.remove(cached)
    jobs.forget(upload_id)

    def work(job):
        pipeline.analyze_upload(upload_id, pdf_path, job=job)

    return jobs.submit(upload_id, work).snapshot()
