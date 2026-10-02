from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.entry import (
    EntryEvent,
    detect_entry_events,
)
from src.metrics.multikill import (
    MultikillRound,
    detect_multikill_rounds,
)
from src.metrics.trade import (
    TradeEvent,
    detect_trade_events,
)


@dataclass(frozen=True)
class MatchStoryEvent:
    steam_id: str
    round_num: int
    event_type: str
    score: float
    evidence: dict[str, int | float | bool] = field(
        default_factory=dict
    )


def select_match_story_events(
    player_steam_ids: Iterable[str],
    *,
    entry_events: Iterable[EntryEvent],
    trade_events: Iterable[TradeEvent],
    multikill_rounds: Iterable[MultikillRound],
) -> dict[str, list[MatchStoryEvent]]:
    """
    Build at most three distinct Match Story events per player:

    - highlight: strongest verified positive round;
    - growth: strongest verified opening-death signal;
    - key: another multi-signal positive round.

    This layer does not invent causality. It only combines already
    verified round-level metrics.
    """

    players = {
        str(steam_id)
        for steam_id in player_steam_ids
        if str(steam_id).strip()
    }

    buckets: dict[
        tuple[str, int],
        dict[str, int | bool],
    ] = defaultdict(
        lambda: {
            "entry_kill": False,
            "entry_death": False,
            "trades_made": 0,
            "was_traded": False,
            "multikill": 0,
        }
    )

    for event in entry_events:
        attacker = str(event.attacker)
        victim = str(event.victim)

        if attacker in players:
            buckets[
                (attacker, event.round_num)
            ]["entry_kill"] = True

        if victim in players:
            buckets[
                (victim, event.round_num)
            ]["entry_death"] = True

    for event in trade_events:
        trader = str(event.trader)
        victim = str(event.victim)

        if trader in players:
            key = (
                trader,
                event.round_num,
            )
            buckets[key]["trades_made"] = (
                int(
                    buckets[key][
                        "trades_made"
                    ]
                )
                + 1
            )

        if victim in players:
            buckets[
                (victim, event.round_num)
            ]["was_traded"] = True

    for event in multikill_rounds:
        steam_id = str(event.steam_id)

        if steam_id not in players:
            continue

        key = (
            steam_id,
            event.round_num,
        )

        buckets[key]["multikill"] = max(
            int(
                buckets[key][
                    "multikill"
                ]
            ),
            int(event.kills),
        )

    result: dict[
        str,
        list[MatchStoryEvent],
    ] = {
        steam_id: []
        for steam_id in players
    }

    for steam_id in players:
        player_rounds = [
            (
                round_num,
                evidence,
            )
            for (
                row_steam_id,
                round_num,
            ), evidence in buckets.items()
            if row_steam_id == steam_id
        ]

        used_rounds: set[int] = set()

        # ----------------------------------------------------------
        # HIGHLIGHT
        # ----------------------------------------------------------

        highlight_candidates = []

        for round_num, evidence in player_rounds:
            kills = int(
                evidence["multikill"]
            )
            entry_kill = bool(
                evidence["entry_kill"]
            )
            trades_made = int(
                evidence["trades_made"]
            )

            strong_enough = (
                kills >= 3
                or (
                    kills >= 2
                    and (
                        entry_kill
                        or trades_made > 0
                    )
                )
                or trades_made >= 2
            )

            if not strong_enough:
                continue

            score = (
                kills * 2.0
                + (
                    2.0
                    if entry_kill
                    else 0.0
                )
                + trades_made * 1.5
            )

            highlight_candidates.append(
                (
                    score,
                    round_num,
                    evidence,
                )
            )

        if highlight_candidates:
            (
                score,
                round_num,
                evidence,
            ) = max(
                highlight_candidates,
                key=lambda item: (
                    item[0],
                    -item[1],
                ),
            )

            result[steam_id].append(
                MatchStoryEvent(
                    steam_id=steam_id,
                    round_num=round_num,
                    event_type="highlight",
                    score=round(
                        score,
                        2,
                    ),
                    evidence={
                        "kills": int(
                            evidence[
                                "multikill"
                            ]
                        ),
                        "entry_kill": bool(
                            evidence[
                                "entry_kill"
                            ]
                        ),
                        "trades_made": int(
                            evidence[
                                "trades_made"
                            ]
                        ),
                    },
                )
            )

            used_rounds.add(
                round_num
            )

        # ----------------------------------------------------------
        # GROWTH
        # ----------------------------------------------------------

        growth_candidates = []

        for round_num, evidence in player_rounds:
            if not bool(
                evidence["entry_death"]
            ):
                continue

            was_traded = bool(
                evidence["was_traded"]
            )

            score = (
                4.5
                if not was_traded
                else 3.0
            )

            growth_candidates.append(
                (
                    score,
                    round_num,
                    evidence,
                )
            )

        if growth_candidates:
            (
                score,
                round_num,
                evidence,
            ) = max(
                growth_candidates,
                key=lambda item: (
                    item[0],
                    -item[1],
                ),
            )

            result[steam_id].append(
                MatchStoryEvent(
                    steam_id=steam_id,
                    round_num=round_num,
                    event_type="growth",
                    score=round(
                        score,
                        2,
                    ),
                    evidence={
                        "entry_death": True,
                        "was_traded": bool(
                            evidence[
                                "was_traded"
                            ]
                        ),
                    },
                )
            )

            used_rounds.add(
                round_num
            )

        # ----------------------------------------------------------
        # KEY EVENT
        # ----------------------------------------------------------

        key_candidates = []

        for round_num, evidence in player_rounds:
            if round_num in used_rounds:
                continue

            kills = int(
                evidence["multikill"]
            )
            entry_kill = bool(
                evidence["entry_kill"]
            )
            trades_made = int(
                evidence["trades_made"]
            )

            signal_count = (
                (1 if kills >= 2 else 0)
                + (1 if entry_kill else 0)
                + (
                    1
                    if trades_made > 0
                    else 0
                )
            )

            if signal_count < 2:
                continue

            score = (
                kills * 2.0
                + (
                    2.0
                    if entry_kill
                    else 0.0
                )
                + trades_made * 1.5
            )

            key_candidates.append(
                (
                    score,
                    round_num,
                    evidence,
                )
            )

        if key_candidates:
            (
                score,
                round_num,
                evidence,
            ) = max(
                key_candidates,
                key=lambda item: (
                    item[0],
                    -item[1],
                ),
            )

            result[steam_id].append(
                MatchStoryEvent(
                    steam_id=steam_id,
                    round_num=round_num,
                    event_type="key",
                    score=round(
                        score,
                        2,
                    ),
                    evidence={
                        "kills": int(
                            evidence[
                                "multikill"
                            ]
                        ),
                        "entry_kill": bool(
                            evidence[
                                "entry_kill"
                            ]
                        ),
                        "trades_made": int(
                            evidence[
                                "trades_made"
                            ]
                        ),
                    },
                )
            )

    return result


def build_match_story_events(
    parser: RawDemoParser,
    player_steam_ids: Iterable[str],
) -> dict[str, list[MatchStoryEvent]]:
    return select_match_story_events(
        player_steam_ids,
        entry_events=detect_entry_events(
            parser
        ),
        trade_events=detect_trade_events(
            parser
        ),
        multikill_rounds=(
            detect_multikill_rounds(
                parser
            )
        ),
    )
