from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUser:
    """
    Authenticated product identity.

    Steam authentication will later become the source of this
    value. API authorization should depend on CurrentUser rather
    than trusting a Steam ID supplied by the browser.
    """

    steam_id: str
