"""
Background analysis jobs.

Analysis runs once, on upload, in a worker thread. Clients poll a cheap
in-memory status endpoint. Nothing about reading a result may ever start
work - that is what previously let a polling frontend spawn a new full
analysis every couple of seconds.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='analysis')
_LOCK = threading.Lock()
_JOBS: dict = {}


@dataclass
class Job:
    id: str
    status: str = 'queued'          # queued | running | complete | error
    stage: str = 'Queued'
    pages_total: int = 0
    pages_done: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def snapshot(self) -> dict:
        payload = {
            'id': self.id,
            'status': self.status,
            'progress': {
                'stage': self.stage,
                'pagesDone': self.pages_done,
                'pagesTotal': self.pages_total,
                'elapsed': round((self.finished_at or time.time()) - self.started_at, 2),
            },
        }
        if self.error:
            payload['error'] = self.error
        if self.result:
            payload.update(self.result)
        return payload


def get_job(job_id: str) -> Optional[Job]:
    with _LOCK:
        return _JOBS.get(job_id)


def _set(job: Job, **kwargs) -> None:
    with _LOCK:
        for key, value in kwargs.items():
            setattr(job, key, value)


def submit(job_id: str, work) -> Job:
    """
    Start `work(job)` in the background.

    `work` receives the Job and should update it as pages finish so partial
    results are visible while later pages are still being read.
    """
    with _LOCK:
        existing = _JOBS.get(job_id)
        if existing and existing.status in ('queued', 'running', 'complete'):
            return existing
        job = Job(id=job_id)
        _JOBS[job_id] = job

    def runner():
        _set(job, status='running', stage='Starting')
        try:
            work(job)
            _set(job, status='complete', stage='Done', finished_at=time.time())
        except Exception as exc:  # noqa: BLE001 - surfaced to the client
            traceback.print_exc()
            _set(job, status='error', error=str(exc), stage='Failed',
                 finished_at=time.time())

    _EXECUTOR.submit(runner)
    return job


def update(job: Job, **kwargs) -> None:
    _set(job, **kwargs)


def forget(job_id: str) -> None:
    with _LOCK:
        _JOBS.pop(job_id, None)


def load_cached(job_id: str, path: str) -> Optional[Job]:
    """Register a completed job from a result file written by an earlier run."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    with _LOCK:
        job = _JOBS.get(job_id)
        if job and job.status in ('running', 'queued'):
            return job
        job = Job(id=job_id, status='complete', stage='Done',
                  pages_total=len(data.get('pages', [])),
                  pages_done=len(data.get('pages', [])),
                  result=data, finished_at=time.time())
        _JOBS[job_id] = job
        return job
