from dataclasses import dataclass
from typing import List

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    build_round_contexts,
    extract_dataframe,
    find_round,
    safe_int,
    valid_sid,
)

from src.metrics.team_context import (
    build_team_state,
    team_relation,
)


@dataclass(frozen=True)
class EntryEvent:
    """One verified opening enemy kill."""

    round_num: int
    attacker: str
    victim: str
    tick: int


def detect_entry_events(
    raw_parser: RawDemoParser,
) -> List[EntryEvent]:
    """
    Return verified opening enemy kills by round.

    Rules:
    - only events inside confirmed rounds;
    - first confirmed enemy kill is the entry event;
    - suicide and teamkill are skipped;
    - unknown team relation blocks the round;
    - equal-tick events preserve original event order;
    - no fixed round-count assumptions.
    """

    rounds = build_round_contexts(
        raw_parser
    )

    if not rounds:
        return []

    try:
        death_events = raw_parser.parse_events(
            ["player_death"]
        )

        df_deaths = extract_dataframe(
            death_events
        )

    except Exception as exc:
        print(
            f"Entry player_death parsing failed: {exc}"
        )
        return []

    if (
        df_deaths is None
        or df_deaths.empty
        or "tick" not in df_deaths.columns
    ):
        return []

    df_deaths = df_deaths.copy()

    df_deaths["_event_order"] = range(
        len(df_deaths)
    )

    df_deaths = df_deaths.sort_values(
        [
            "tick",
            "_event_order",
        ],
        kind="stable",
    )

    death_ticks = sorted({
        safe_int(
            row.get("tick"),
            default=-1,
        )
        for _, row in df_deaths.iterrows()
        if find_round(
            row.get("tick"),
            rounds,
        ) is not None
    })

    if not death_ticks:
        return []

    team_at_tick = build_team_state(
        raw_parser,
        death_ticks,
    )

    if not team_at_tick:
        return []

    opened_rounds = set()
    blocked_rounds = set()

    detected: List[EntryEvent] = []

    for _, row in df_deaths.iterrows():

        tick = safe_int(
            row.get("tick"),
            default=-1,
        )

        round_context = find_round(
            tick,
            rounds,
        )

        if round_context is None:
            continue

        round_num = (
            round_context.round_num
        )

        if round_num in opened_rounds:
            continue

        if round_num in blocked_rounds:
            continue

        attacker = str(
            row.get(
                "attacker_steamid",
                "",
            )
        )

        victim = str(
            row.get(
                "user_steamid",
                "",
            )
        )

        if not valid_sid(victim):
            continue

        if not valid_sid(attacker):
            continue

        if attacker == victim:
            continue

        relation = team_relation(
            team_at_tick,
            tick,
            attacker,
            victim,
        )

        if relation == "teammate":
            continue

        if relation == "unknown":
            blocked_rounds.add(
                round_num
            )
            continue

        if relation != "enemy":
            continue

        detected.append(
            EntryEvent(
                round_num=round_num,
                attacker=attacker,
                victim=victim,
                tick=tick,
            )
        )

        opened_rounds.add(
            round_num
        )

    if blocked_rounds:
        print(
            "Entry not calculated for rounds with "
            "unknown team relation: "
            f"{sorted(blocked_rounds)}"
        )

    return detected


def calculate_entry_metrics(
    raw_parser: RawDemoParser
) -> dict:
    """
    Calculate aggregate verified Entry Kill / Entry Death counts.
    """

    stats = {}

    for event in detect_entry_events(
        raw_parser
    ):

        for steam_id in (
            event.attacker,
            event.victim,
        ):
            if steam_id not in stats:
                stats[steam_id] = {
                    "entry_kills": 0,
                    "entry_deaths": 0,
                }

        stats[
            event.attacker
        ]["entry_kills"] += 1

        stats[
            event.victim
        ]["entry_deaths"] += 1

    return stats
