from __future__ import annotations

from dataclasses import dataclass
import time

import httpx


STEAM_PLAYER_SUMMARIES_URL = (
    "https://api.steampowered.com/"
    "ISteamUser/GetPlayerSummaries/v0002/"
)

CACHE_TTL_SECONDS = 300.0


@dataclass(frozen=True)
class SteamProfile:
    player_name: str
    avatar_url: str


_profile_cache: dict[
    str,
    tuple[float, SteamProfile],
] = {}


def fetch_steam_profile(
    *,
    steam_id: str,
    api_key: str,
) -> SteamProfile | None:
    if not api_key:
        return None

    now = time.monotonic()

    cached = _profile_cache.get(
        steam_id
    )

    if cached is not None:
        cached_at, profile = cached

        if (
            now - cached_at
            < CACHE_TTL_SECONDS
        ):
            return profile

    try:
        response = httpx.get(
            STEAM_PLAYER_SUMMARIES_URL,
            params={
                "key": api_key,
                "steamids": steam_id,
            },
            timeout=5.0,
        )

        response.raise_for_status()

        payload = response.json()

        players = (
            payload
            .get("response", {})
            .get("players", [])
        )

        if not players:
            return None

        player = players[0]

        player_name = str(
            player.get(
                "personaname",
                ""
            )
        ).strip()

        avatar_url = str(
            player.get(
                "avatarfull",
                ""
            )
        ).strip()

        if not player_name:
            return None

        profile = SteamProfile(
            player_name=player_name,
            avatar_url=avatar_url,
        )

        _profile_cache[steam_id] = (
            now,
            profile,
        )

        return profile

    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
    ):
        return None
