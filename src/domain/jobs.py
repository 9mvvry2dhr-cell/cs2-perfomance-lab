from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


JobStatus = Literal[
    "queued",
    "processing",
    "completed",
    "failed",
]


@dataclass(frozen=True)
class AnalysisJob:
    id: str
    status: JobStatus

    original_filename: str
    storage_key: str
    file_sha256: str

    match_id: str | None
    error: str | None

    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
