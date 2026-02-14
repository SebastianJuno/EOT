from __future__ import annotations

import copy
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class ProgressJob:
    job_id: str
    operation: str
    status: JobStatus = "queued"
    progress_pct: float = 0.0
    stage: str = "Queued"
    detail: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: dict[str, Any] | None = None
    error: str | None = None


class ProgressJobStore:
    def __init__(self, *, ttl_seconds: int = 600, max_jobs: int = 64) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_jobs = max_jobs
        self._jobs: dict[str, ProgressJob] = {}
        self._lock = threading.Lock()

    def create_job(self, operation: str) -> str:
        with self._lock:
            self._cleanup_locked()
            job_id = uuid.uuid4().hex[:16]
            self._jobs[job_id] = ProgressJob(job_id=job_id, operation=operation)
            return job_id

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress_pct: float | None = None,
        stage: str | None = None,
        detail: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if status is not None:
                job.status = status
            if progress_pct is not None:
                job.progress_pct = max(0.0, min(100.0, float(progress_pct)))
            if stage is not None:
                job.stage = stage
            if detail is not None:
                job.detail = detail
            job.updated_at = time.time()

    def complete_job(self, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "completed"
            job.progress_pct = 100.0
            job.stage = "Completed"
            job.detail = ""
            job.result = result
            job.error = None
            job.updated_at = time.time()

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "failed"
            job.stage = "Failed"
            job.detail = ""
            job.error = error
            job.updated_at = time.time()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return copy.deepcopy(job.__dict__)

    def cleanup(self) -> None:
        with self._lock:
            self._cleanup_locked()

    def _cleanup_locked(self) -> None:
        now = time.time()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if now - job.updated_at > self._ttl_seconds
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)

        while len(self._jobs) > self._max_jobs:
            oldest = min(self._jobs.values(), key=lambda item: item.updated_at)
            self._jobs.pop(oldest.job_id, None)
