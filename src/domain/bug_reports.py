from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BugReport:
    id: str
    owner_steam_id: str
    category: str
    message: str
    match_id: str | None
    job_id: str | None
    created_at: datetime
