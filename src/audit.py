from __future__ import annotations

import hashlib
import json
import logging
from typing import Any


logger = logging.getLogger("cs2.audit")


def audit_actor_id(
    steam_id: str | None,
) -> str | None:
    """
    Produce a stable pseudonymous actor id for logs.

    Raw Steam IDs, session cookies, IP addresses and user agents
    are intentionally excluded from the audit journal.
    """
    if steam_id is None:
        return None

    normalized = steam_id.strip()

    if not normalized:
        return None

    digest = hashlib.sha256(
        (
            "cs2pl-audit:"
            + normalized
        ).encode("utf-8")
    ).hexdigest()

    return digest[:16]


def audit_event(
    event: str,
    *,
    steam_id: str | None = None,
    status: str = "success",
    **details: Any,
) -> None:
    """
    Write one structured audit event to application logs.

    Keep details deliberately small and non-sensitive. Callers
    should pass identifiers and operational counters, never raw
    demo contents, cookies, OpenAI prompts/responses or bug text.
    """
    payload: dict[str, Any] = {
        "event": event,
        "status": status,
    }

    actor = audit_actor_id(
        steam_id
    )

    if actor is not None:
        payload["actor"] = actor

    for key, value in details.items():
        if value is not None:
            payload[key] = value

    logger.info(
        "AUDIT %s",
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
    )
