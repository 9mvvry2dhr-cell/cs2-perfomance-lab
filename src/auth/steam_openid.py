from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


STEAM_OPENID_ENDPOINT = (
    "https://steamcommunity.com/openid/login"
)

OPENID_NS = (
    "http://specs.openid.net/auth/2.0"
)

OPENID_IDENTIFIER_SELECT = (
    "http://specs.openid.net/auth/2.0/"
    "identifier_select"
)

STEAM_CLAIMED_ID_RE = re.compile(
    r"^https://steamcommunity\.com/openid/id/"
    r"(?P<steam_id>[0-9]+)$"
)


class SteamOpenIDError(RuntimeError):
    pass


def build_steam_login_url(
    *,
    return_to: str,
    realm: str,
) -> str:
    if not return_to:
        raise ValueError(
            "return_to must not be empty"
        )

    if not realm:
        raise ValueError(
            "realm must not be empty"
        )

    params = {
        "openid.ns": OPENID_NS,
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": (
            OPENID_IDENTIFIER_SELECT
        ),
        "openid.claimed_id": (
            OPENID_IDENTIFIER_SELECT
        ),
    }

    return (
        f"{STEAM_OPENID_ENDPOINT}?"
        f"{urlencode(params)}"
    )


def verify_steam_openid_response(
    params: Mapping[str, str],
    *,
    timeout: float = 10.0,
) -> str:
    if params.get("openid.mode") != "id_res":
        raise SteamOpenIDError(
            "Steam OpenID response is not id_res"
        )

    if params.get("openid.ns") != OPENID_NS:
        raise SteamOpenIDError(
            "Unexpected OpenID namespace"
        )

    op_endpoint = params.get(
        "openid.op_endpoint",
        "",
    )

    if op_endpoint.rstrip("/") != (
        STEAM_OPENID_ENDPOINT.rstrip("/")
    ):
        raise SteamOpenIDError(
            "Unexpected OpenID provider"
        )

    claimed_id = params.get(
        "openid.claimed_id",
        "",
    )

    identity = params.get(
        "openid.identity",
        "",
    )

    if claimed_id != identity:
        raise SteamOpenIDError(
            "OpenID identity does not match claimed_id"
        )

    match = STEAM_CLAIMED_ID_RE.fullmatch(
        claimed_id
    )

    if match is None:
        raise SteamOpenIDError(
            "Invalid Steam claimed_id"
        )

    verification_params = dict(params)
    verification_params[
        "openid.mode"
    ] = "check_authentication"

    body = urlencode(
        verification_params
    ).encode("utf-8")

    request = Request(
        STEAM_OPENID_ENDPOINT,
        data=body,
        headers={
            "Content-Type": (
                "application/"
                "x-www-form-urlencoded"
            ),
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            result = response.read().decode(
                "utf-8"
            )

    except (OSError, URLError) as exc:
        raise SteamOpenIDError(
            "Steam OpenID verification failed"
        ) from exc

    verification = {}

    for line in result.splitlines():
        key, separator, value = (
            line.partition(":")
        )

        if separator:
            verification[
                key.strip()
            ] = value.strip()

    if verification.get(
        "is_valid"
    ) != "true":
        raise SteamOpenIDError(
            "Steam rejected OpenID response"
        )

    steam_id = match.group(
        "steam_id"
    )

    if (
        not steam_id.isdigit()
        or len(steam_id) > 20
    ):
        raise SteamOpenIDError(
            "Invalid SteamID64"
        )

    return steam_id
