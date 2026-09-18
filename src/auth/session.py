from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime


SESSION_TOKEN_BYTES = 32


@dataclass(frozen=True)
class AuthenticatedSession:
    steam_id: str
    session_id: str
    expires_at: datetime


def generate_session_token() -> str:
    """
    Generate an opaque high-entropy token for the browser.

    The raw value must never be persisted in the database.
    """
    return secrets.token_urlsafe(
        SESSION_TOKEN_BYTES
    )


def hash_session_token(
    token: str,
) -> str:
    """
    Persist only the SHA-256 digest of the opaque token.
    """
    if not token:
        raise ValueError(
            "Session token must not be empty"
        )

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()
