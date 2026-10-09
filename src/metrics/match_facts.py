from __future__ import annotations

import json
import math
import zlib
from typing import Any, Iterable

import pandas as pd


MATCH_FACTS_VERSION = 1

MATCH_FACTS_CAPABILITIES = [
    "rounds",
    "team_context",
    "combat",
    "utility",
    "weapon_fire",
    "bomb",
    "grenade_detonations",
    "grenade_positions",
]


# Stored as:
#
# {
#   "facts_version": 1,
#   "capabilities": [...],
#   "player_count": 10,
#   "captured": [...],
#   "events": {
#       "player_hurt": {
#           "columns": [...],
#           "rows": [[...], ...],
#       },
#   },
# }
#
# Player references are positional integers only.
# Steam IDs and player names must never enter the payload.


EVENT_SPECS: dict[
    str,
    list[tuple[str, str, str]],
] = {
    "player_hurt": [
        ("tick", "tick", "int"),
        ("attacker", "attacker_steamid", "player"),
        ("victim", "user_steamid", "player"),
        ("weapon", "weapon", "str"),
        ("dmg_health", "dmg_health", "float"),
        ("health", "health", "float"),
        ("dmg_armor", "dmg_armor", "float"),
        ("armor", "armor", "float"),
        ("hitgroup", "hitgroup", "int"),
    ],
    "player_death": [
        ("tick", "tick", "int"),
        ("attacker", "attacker_steamid", "player"),
        ("victim", "user_steamid", "player"),
        ("assister", "assister_steamid", "player"),
        ("weapon", "weapon", "str"),
        ("headshot", "headshot", "bool"),
        ("distance", "distance", "float"),
        ("penetrated", "penetrated", "int"),
        ("thrusmoke", "thrusmoke", "bool"),
        ("noscope", "noscope", "bool"),
        ("attackerblind", "attackerblind", "bool"),
        ("attackerinair", "attackerinair", "bool"),
        ("assistedflash", "assistedflash", "bool"),
        ("hitgroup", "hitgroup", "int"),
    ],
    "player_blind": [
        ("tick", "tick", "int"),
        ("attacker", "attacker_steamid", "player"),
        ("victim", "user_steamid", "player"),
        ("duration", "blind_duration", "float"),
        ("entity", "entityid", "int"),
    ],
    "weapon_fire": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("weapon", "weapon", "str"),
        ("silenced", "silenced", "bool"),
    ],
    "begin_new_match": [
        ("tick", "tick", "int"),
    ],
    "round_start": [
        ("tick", "tick", "int"),
        ("round", "round", "int"),
    ],
    "round_freeze_end": [
        ("tick", "tick", "int"),
    ],
    "round_end": [
        ("tick", "tick", "int"),
        ("round", "round", "int"),
        ("winner", "winner", "str"),
        ("reason", "reason", "str"),
    ],
    "cs_win_panel_match": [
        ("tick", "tick", "int"),
    ],
    "bomb_planted": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("site", "site", "str"),
        ("entity", "c4", "int"),
    ],
    "bomb_defused": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("site", "site", "str"),
        ("entity", "c4", "int"),
    ],
    "bomb_exploded": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("site", "site", "str"),
        ("entity", "c4", "int"),
    ],
    "hegrenade_detonate": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("entity", "entityid", "int"),
        ("x", "x", "float"),
        ("y", "y", "float"),
        ("z", "z", "float"),
    ],
    "flashbang_detonate": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("entity", "entityid", "int"),
        ("x", "x", "float"),
        ("y", "y", "float"),
        ("z", "z", "float"),
    ],
    "smokegrenade_detonate": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("entity", "entityid", "int"),
        ("x", "x", "float"),
        ("y", "y", "float"),
        ("z", "z", "float"),
    ],
    "inferno_startburn": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("entity", "entityid", "int"),
        ("x", "x", "float"),
        ("y", "y", "float"),
        ("z", "z", "float"),
    ],
    "inferno_expire": [
        ("tick", "tick", "int"),
        ("user", "user_steamid", "player"),
        ("entity", "entityid", "int"),
        ("x", "x", "float"),
        ("y", "y", "float"),
        ("z", "z", "float"),
    ],
}


CAPTURED = [
    "combat_events",
    "weapon_fire",
    "blind_events",
    "round_events",
    "bomb_events",
    "grenade_detonations",
    "grenade_positions",
    "team_snapshots",
]


def _steam_key(
    value: object,
) -> str | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip()

    if not text:
        return None

    try:
        return str(int(value))
    except (TypeError, ValueError, OverflowError):
        return text


def _scalar(
    value: object,
) -> object:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass

    if isinstance(
        value,
        float,
    ) and not math.isfinite(value):
        return None

    return value


def _convert(
    value: object,
    kind: str,
    player_by_steam: dict[str, int],
) -> object:
    value = _scalar(value)

    if value is None:
        return None

    if kind == "player":
        key = _steam_key(value)

        if key is None:
            return None

        return player_by_steam.get(
            key
        )

    if kind == "int":
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return None

    if kind == "float":
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            return None

        return (
            result
            if math.isfinite(result)
            else None
        )

    if kind == "bool":
        return bool(value)

    if kind == "str":
        return str(value)

    raise ValueError(
        f"Unsupported fact kind: {kind}"
    )


def _event_frame(
    raw_parser: Any,
    event_name: str,
) -> pd.DataFrame:
    parsed = raw_parser.parse_events(
        [event_name]
    )

    for item in parsed:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and item[0] == event_name
            and isinstance(
                item[1],
                pd.DataFrame,
            )
        ):
            return item[1]

    return pd.DataFrame()



def _build_team_snapshots(
    raw_parser: Any,
    player_by_steam: dict[str, int],
) -> dict[str, Any]:
    freeze_frame = _event_frame(
        raw_parser,
        "round_freeze_end",
    )

    if (
        freeze_frame.empty
        or "tick"
        not in freeze_frame.columns
    ):
        return {
            "columns": [
                "tick",
                "player",
                "team_num",
            ],
            "rows": [],
        }

    ticks: list[int] = []

    for value in (
        freeze_frame["tick"]
        .dropna()
        .tolist()
    ):
        try:
            ticks.append(
                int(value)
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            continue

    ticks = sorted(
        set(ticks)
    )

    if not ticks:
        return {
            "columns": [
                "tick",
                "player",
                "team_num",
            ],
            "rows": [],
        }

    try:
        frame = raw_parser.parse_ticks(
            ["team_num"],
            ticks=ticks,
        )
    except Exception:
        frame = pd.DataFrame()

    if (
        frame is None
        or not isinstance(
            frame,
            pd.DataFrame,
        )
        or frame.empty
    ):
        return {
            "columns": [
                "tick",
                "player",
                "team_num",
            ],
            "rows": [],
        }

    required = {
        "tick",
        "steamid",
        "team_num",
    }

    if not required.issubset(
        set(frame.columns)
    ):
        return {
            "columns": [
                "tick",
                "player",
                "team_num",
            ],
            "rows": [],
        }

    snapshots: dict[
        tuple[int, int],
        int,
    ] = {}

    for _, row in frame.iterrows():
        steam_key = _steam_key(
            row.get("steamid")
        )

        if steam_key is None:
            continue

        player = player_by_steam.get(
            steam_key
        )

        if player is None:
            continue

        try:
            tick = int(
                row.get("tick")
            )

            team_num = int(
                row.get("team_num")
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            continue

        snapshots[
            (
                tick,
                player,
            )
        ] = team_num

    rows = [
        [
            tick,
            player,
            team_num,
        ]
        for (
            tick,
            player,
        ), team_num in sorted(
            snapshots.items()
        )
    ]

    return {
        "columns": [
            "tick",
            "player",
            "team_num",
        ],
        "rows": rows,
    }



def build_match_facts(
    raw_parser: Any,
    player_steam_ids: Iterable[object],
) -> dict[str, Any]:
    player_by_steam: dict[
        str,
        int,
    ] = {}

    for position, steam_id in enumerate(
        player_steam_ids
    ):
        key = _steam_key(
            steam_id
        )

        if key is None:
            continue

        if key in player_by_steam:
            raise ValueError(
                "Duplicate player Steam ID "
                "while building match facts"
            )

        player_by_steam[key] = (
            position
        )

    events: dict[
        str,
        dict[str, Any],
    ] = {}

    for (
        event_name,
        spec,
    ) in EVENT_SPECS.items():
        frame = _event_frame(
            raw_parser,
            event_name,
        )

        columns = [
            output_name
            for (
                output_name,
                _,
                _,
            ) in spec
        ]

        rows: list[list[object]] = []

        if not frame.empty:
            for _, source_row in (
                frame.iterrows()
            ):
                packed = [
                    _convert(
                        source_row.get(
                            source_name
                        ),
                        kind,
                        player_by_steam,
                    )
                    for (
                        _output_name,
                        source_name,
                        kind,
                    ) in spec
                ]

                rows.append(
                    packed
                )

        events[event_name] = {
            "columns": columns,
            "rows": rows,
        }

    team_snapshots = (
        _build_team_snapshots(
            raw_parser,
            player_by_steam,
        )
    )

    return {
        "facts_version": (
            MATCH_FACTS_VERSION
        ),
        "capabilities": list(
            MATCH_FACTS_CAPABILITIES
        ),
        "player_count": len(
            player_by_steam
        ),
        "captured": list(
            CAPTURED
        ),
        "events": events,
        "team_snapshots": (
            team_snapshots
        ),
    }



class FactsReplayParser:
    """
    Minimal demoparser-compatible facade.

    It reconstructs only the parser surface
    covered by Match Facts v1.

    No real Steam ID or nickname is restored.
    """

    _STEAM_BASE = (
        76561199000000000
    )

    def __init__(
        self,
        facts: dict[str, Any],
    ) -> None:
        version = int(
            facts.get(
                "facts_version",
                0,
            )
        )

        if version != MATCH_FACTS_VERSION:
            raise ValueError(
                "Unsupported match facts "
                f"version: {version}"
            )

        self.facts = facts

        self.player_count = int(
            facts.get(
                "player_count",
                0,
            )
        )

        self.player_steam_ids = [
            self._synthetic_steam_id(
                position
            )
            for position in range(
                self.player_count
            )
        ]

    @classmethod
    def _synthetic_steam_id(
        cls,
        position: int,
    ) -> str:
        return str(
            cls._STEAM_BASE
            + int(position)
            + 1
        )

    @staticmethod
    def _synthetic_name(
        position: int,
    ) -> str:
        return (
            f"Player {position + 1}"
        )

    def parse_events(
        self,
        event_names: Iterable[str],
    ) -> list[
        tuple[
            str,
            pd.DataFrame,
        ]
    ]:
        result: list[
            tuple[
                str,
                pd.DataFrame,
            ]
        ] = []

        stored_events = (
            self.facts.get(
                "events",
                {}
            )
        )

        for event_name in event_names:
            spec = EVENT_SPECS.get(
                event_name
            )

            if spec is None:
                result.append(
                    (
                        event_name,
                        pd.DataFrame(),
                    )
                )
                continue

            block = stored_events.get(
                event_name,
                {},
            )

            packed_columns = list(
                block.get(
                    "columns",
                    [],
                )
            )

            packed_rows = list(
                block.get(
                    "rows",
                    [],
                )
            )

            column_index = {
                name: index
                for index, name
                in enumerate(
                    packed_columns
                )
            }

            rows: list[
                dict[str, object]
            ] = []

            for packed in packed_rows:
                row: dict[
                    str,
                    object
                ] = {}

                for (
                    stored_name,
                    source_name,
                    kind,
                ) in spec:
                    index = (
                        column_index.get(
                            stored_name
                        )
                    )

                    if (
                        index is None
                        or index
                        >= len(packed)
                    ):
                        value = None
                    else:
                        value = packed[
                            index
                        ]

                    if (
                        kind == "player"
                        and value is not None
                    ):
                        position = int(
                            value
                        )

                        value = (
                            self
                            ._synthetic_steam_id(
                                position
                            )
                        )

                        row[
                            source_name
                        ] = value

                        if source_name.endswith(
                            "_steamid"
                        ):
                            prefix = (
                                source_name[
                                    :-8
                                ]
                            )

                            row[
                                f"{prefix}_name"
                            ] = (
                                self
                                ._synthetic_name(
                                    position
                                )
                            )

                    else:
                        row[
                            source_name
                        ] = value

                rows.append(
                    row
                )

            frame = pd.DataFrame(
                rows
            )

            result.append(
                (
                    event_name,
                    frame,
                )
            )

        return result

    def parse_ticks(
        self,
        properties: Iterable[str],
        *,
        ticks: Iterable[int] | None = None,
    ) -> pd.DataFrame:
        properties = list(
            properties
        )

        unsupported = [
            item
            for item in properties
            if item != "team_num"
        ]

        if unsupported:
            raise ValueError(
                "Facts v1 cannot replay "
                "tick properties: "
                + ", ".join(
                    unsupported
                )
            )

        block = self.facts.get(
            "team_snapshots",
            {},
        )

        columns = list(
            block.get(
                "columns",
                [],
            )
        )

        rows = list(
            block.get(
                "rows",
                [],
            )
        )

        index = {
            name: pos
            for pos, name
            in enumerate(columns)
        }

        required = {
            "tick",
            "player",
            "team_num",
        }

        if not required.issubset(
            index
        ):
            return pd.DataFrame(
                columns=[
                    "team_num",
                    "tick",
                    "steamid",
                    "name",
                ]
            )

        snapshots: dict[
            int,
            list[
                tuple[int, int]
            ],
        ] = {}

        for packed in rows:
            snapshot_tick = int(
                packed[
                    index["tick"]
                ]
            )

            player = int(
                packed[
                    index["player"]
                ]
            )

            team_num = int(
                packed[
                    index["team_num"]
                ]
            )

            snapshots.setdefault(
                snapshot_tick,
                [],
            ).append(
                (
                    player,
                    team_num,
                )
            )

        snapshot_ticks = sorted(
            snapshots
        )

        if not snapshot_ticks:
            return pd.DataFrame(
                columns=[
                    "team_num",
                    "tick",
                    "steamid",
                    "name",
                ]
            )

        if ticks is None:
            requested_ticks = (
                snapshot_ticks
            )
        else:
            requested_ticks = sorted(
                {
                    int(value)
                    for value in ticks
                }
            )

        restored: list[
            dict[str, object]
        ] = []

        for requested_tick in requested_ticks:
            source_tick = None

            for snapshot_tick in (
                snapshot_ticks
            ):
                if (
                    snapshot_tick
                    > requested_tick
                ):
                    break

                source_tick = (
                    snapshot_tick
                )

            if source_tick is None:
                continue

            for (
                player,
                team_num,
            ) in snapshots[
                source_tick
            ]:
                restored.append(
                    {
                        "team_num":
                            team_num,
                        "tick":
                            requested_tick,
                        "steamid":
                            self
                            ._synthetic_steam_id(
                                player
                            ),
                        "name":
                            self
                            ._synthetic_name(
                                player
                            ),
                    }
                )

        return pd.DataFrame(
            restored,
            columns=[
                "team_num",
                "tick",
                "steamid",
                "name",
            ],
        )


def encode_match_facts(
    facts: dict[str, Any],
) -> bytes:
    raw = json.dumps(
        facts,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(
        "utf-8"
    )

    return zlib.compress(
        raw,
        level=9,
    )


def decode_match_facts(
    payload: bytes,
) -> dict[str, Any]:
    raw = zlib.decompress(
        payload
    )

    decoded = json.loads(
        raw.decode("utf-8")
    )

    if not isinstance(
        decoded,
        dict,
    ):
        raise ValueError(
            "Invalid match facts payload"
        )

    return decoded
