from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from demoparser2 import DemoParser as RawDemoParser

from src.metrics.round_context import (
    RoundContext,
    build_round_contexts,
    extract_dataframe,
    find_round,
    safe_int,
    valid_sid,
)


TEAM_T = 2
TEAM_CT = 3
VALID_TEAMS = {
    TEAM_T,
    TEAM_CT,
}


@dataclass(frozen=True)
class RoundStateTransition:
    """
    One confirmed change in alive-player state.

    Counts are always explicit by side:
        T alive
        CT alive

    The engine intentionally does not infer tactical causality.
    It records only verified roster/death state.
    """

    round_num: int
    tick: int

    attacker: str | None
    victim: str

    attacker_team: int | None
    victim_team: int

    cause: str

    t_alive_before: int
    ct_alive_before: int

    t_alive_after: int
    ct_alive_after: int

    @property
    def state_before(self) -> str:
        return (
            f"T{self.t_alive_before}"
            f"-CT{self.ct_alive_before}"
        )

    @property
    def state_after(self) -> str:
        return (
            f"T{self.t_alive_after}"
            f"-CT{self.ct_alive_after}"
        )


@dataclass(frozen=True)
class RoundAdvantageSummary:
    """
    Deterministic round-level advantage summary.

    first_advantage_team:
        first side to gain a numerical alive-player lead.

    converted_first_advantage:
        whether that side eventually won the round.

    advantage_lost:
        whether the first advantaged side later stopped
        having a numerical lead.

    advantage_restored:
        whether it later regained a numerical lead.

    comeback_team:
        round winner when that winner had previously been
        numerically behind at least once.
    """

    round_num: int
    winner_team: int | None

    first_advantage_team: int | None
    first_advantage_tick: int | None
    first_advantage_by: str | None

    converted_first_advantage: bool | None

    advantage_lost: bool
    advantage_restored: bool

    comeback_team: int | None

    max_t_advantage: int
    max_ct_advantage: int

    @property
    def advantage_reversed(self) -> bool:
        """
        Whether the opponent of the first advantaged team
        later gained a real numerical lead.

        A return to equal numbers alone is not a reversal.
        """
        if self.first_advantage_team == TEAM_T:
            return self.max_ct_advantage > 0

        if self.first_advantage_team == TEAM_CT:
            return self.max_t_advantage > 0

        return False


def _team_from_value(
    value,
) -> int | None:
    team = safe_int(
        value,
        default=-1,
    )

    if team in VALID_TEAMS:
        return team

    return None


def _alive_difference(
    *,
    t_alive: int,
    ct_alive: int,
) -> int:
    """
    Positive = T numerical advantage.
    Negative = CT numerical advantage.
    """

    return (
        t_alive
        - ct_alive
    )


def _leading_team(
    *,
    t_alive: int,
    ct_alive: int,
) -> int | None:
    difference = _alive_difference(
        t_alive=t_alive,
        ct_alive=ct_alive,
    )

    if difference > 0:
        return TEAM_T

    if difference < 0:
        return TEAM_CT

    return None


def _build_round_rosters(
    parser: RawDemoParser,
    rounds: Iterable[RoundContext],
) -> dict[
    int,
    dict[str, int],
]:
    """
    Build the verified live roster at freeze_end.

    A player is included only when:
    - SteamID is valid;
    - team_num is T or CT;
    - health > 0.

    This keeps late joins/disconnect noise away from
    the round's initial 5v5/4v5/etc state.
    """

    rounds = list(
        rounds
    )

    freeze_ticks = sorted({
        round_context.freeze_end_tick
        for round_context in rounds
        if round_context.freeze_end_tick >= 0
    })

    if not freeze_ticks:
        return {}

    try:
        df = parser.parse_ticks(
            [
                "team_num",
                "health",
            ],
            ticks=freeze_ticks,
        )

    except Exception:
        return {}

    required = {
        "tick",
        "steamid",
        "team_num",
        "health",
    }

    if (
        df is None
        or not hasattr(
            df,
            "empty",
        )
        or df.empty
        or not required.issubset(
            df.columns
        )
    ):
        return {}

    round_by_freeze_tick = {
        round_context.freeze_end_tick:
        round_context.round_num
        for round_context in rounds
    }

    rosters: dict[
        int,
        dict[str, int],
    ] = {
        round_context.round_num: {}
        for round_context in rounds
    }

    for _, row in df.iterrows():
        tick = safe_int(
            row.get(
                "tick"
            ),
            default=-1,
        )

        round_num = (
            round_by_freeze_tick.get(
                tick
            )
        )

        if round_num is None:
            continue

        steam_id = str(
            row.get(
                "steamid",
                "",
            )
        )

        if not valid_sid(
            steam_id
        ):
            continue

        team = _team_from_value(
            row.get(
                "team_num"
            )
        )

        if team is None:
            continue

        health = safe_int(
            row.get(
                "health"
            ),
            default=0,
        )

        if health <= 0:
            continue

        rosters[
            round_num
        ][steam_id] = team

    return rosters


def _classify_death(
    *,
    attacker: str,
    victim: str,
    attacker_team: int | None,
    victim_team: int,
) -> str:
    if (
        not valid_sid(
            attacker
        )
    ):
        return "world"

    if attacker == victim:
        return "suicide"

    if attacker_team is None:
        return "unknown"

    if (
        attacker_team
        == victim_team
    ):
        return "teamkill"

    return "enemy"


def build_round_state_transitions(
    parser: RawDemoParser,
) -> list[RoundStateTransition]:
    """
    Build chronological alive-state transitions for all
    confirmed played rounds.

    Every victim can leave the alive set only once per round.
    Duplicate death events are ignored.

    World deaths, suicides and teamkills still change alive
    counts because they genuinely change the round state.
    """

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return []

    rosters = _build_round_rosters(
        parser,
        rounds,
    )

    if not rosters:
        return []

    try:
        events = parser.parse_event(
            "player_death"
        )

        df = extract_dataframe(
            events
        )

    except Exception:
        return []

    required = {
        "tick",
        "user_steamid",
    }

    if (
        df is None
        or not hasattr(
            df,
            "empty",
        )
        or df.empty
        or not required.issubset(
            df.columns
        )
    ):
        return []

    df = df.copy()

    df["_event_order"] = range(
        len(df)
    )

    df = df.sort_values(
        [
            "tick",
            "_event_order",
        ],
        kind="stable",
    )

    alive_by_round: dict[
        int,
        set[str],
    ] = {
        round_num: set(
            roster.keys()
        )
        for round_num, roster
        in rosters.items()
    }

    transitions: list[
        RoundStateTransition
    ] = []

    for _, row in df.iterrows():
        tick = safe_int(
            row.get(
                "tick"
            ),
            default=-1,
        )

        if tick < 0:
            continue

        round_context = find_round(
            tick,
            rounds,
        )

        if round_context is None:
            continue

        round_num = (
            round_context.round_num
        )

        roster = rosters.get(
            round_num,
            {},
        )

        alive = alive_by_round.get(
            round_num
        )

        if alive is None:
            continue

        victim = str(
            row.get(
                "user_steamid",
                "",
            )
        )

        if (
            not valid_sid(
                victim
            )
            or victim not in roster
            or victim not in alive
        ):
            continue

        victim_team = roster[
            victim
        ]

        attacker = str(
            row.get(
                "attacker_steamid",
                "",
            )
        )

        attacker_team = (
            roster.get(
                attacker
            )
            if valid_sid(
                attacker
            )
            else None
        )

        t_before = sum(
            1
            for steam_id in alive
            if roster.get(
                steam_id
            ) == TEAM_T
        )

        ct_before = sum(
            1
            for steam_id in alive
            if roster.get(
                steam_id
            ) == TEAM_CT
        )

        alive.remove(
            victim
        )

        t_after = sum(
            1
            for steam_id in alive
            if roster.get(
                steam_id
            ) == TEAM_T
        )

        ct_after = sum(
            1
            for steam_id in alive
            if roster.get(
                steam_id
            ) == TEAM_CT
        )

        transitions.append(
            RoundStateTransition(
                round_num=round_num,
                tick=tick,
                attacker=(
                    attacker
                    if valid_sid(
                        attacker
                    )
                    else None
                ),
                victim=victim,
                attacker_team=(
                    attacker_team
                    if attacker_team
                    in VALID_TEAMS
                    else None
                ),
                victim_team=(
                    victim_team
                ),
                cause=_classify_death(
                    attacker=attacker,
                    victim=victim,
                    attacker_team=(
                        attacker_team
                    ),
                    victim_team=(
                        victim_team
                    ),
                ),
                t_alive_before=t_before,
                ct_alive_before=(
                    ct_before
                ),
                t_alive_after=t_after,
                ct_alive_after=(
                    ct_after
                ),
            )
        )

    return transitions


def summarize_round_advantage(
    parser: RawDemoParser,
    *,
    transitions: Optional[
        list[
            RoundStateTransition
        ]
    ] = None,
) -> list[RoundAdvantageSummary]:
    """
    Convert state transitions into round-level
    Advantage Control metrics.
    """

    rounds = build_round_contexts(
        parser
    )

    if not rounds:
        return []

    if transitions is None:
        transitions = (
            build_round_state_transitions(
                parser
            )
        )

    rosters = _build_round_rosters(
        parser,
        rounds,
    )

    by_round: dict[
        int,
        list[
            RoundStateTransition
        ],
    ] = {
        round_context.round_num: []
        for round_context in rounds
    }

    for transition in transitions:
        by_round.setdefault(
            transition.round_num,
            [],
        ).append(
            transition
        )

    summaries: list[
        RoundAdvantageSummary
    ] = []

    for round_context in rounds:
        round_transitions = sorted(
            by_round.get(
                round_context.round_num,
                [],
            ),
            key=lambda item: (
                item.tick
            ),
        )

        roster = rosters.get(
            round_context.round_num,
            {},
        )

        initial_t_alive = sum(
            1
            for team in roster.values()
            if team == TEAM_T
        )

        initial_ct_alive = sum(
            1
            for team in roster.values()
            if team == TEAM_CT
        )

        initial_leader = _leading_team(
            t_alive=initial_t_alive,
            ct_alive=initial_ct_alive,
        )

        first_advantage_team = (
            initial_leader
        )

        first_advantage_tick = (
            round_context.freeze_end_tick
            if initial_leader
            in VALID_TEAMS
            else None
        )

        # No individual player "created" an advantage
        # that already existed at freeze_end.
        first_advantage_by = None

        advantage_lost = False
        advantage_restored = False

        first_team_has_lost = False

        # Prefer confirmed transition states when deaths exist.
        # Freeze-end roster snapshots can occasionally disagree
        # with the first confirmed state in unusual demos.
        winner_was_behind = (
            not round_transitions
            and round_context.winner_team
            in VALID_TEAMS
            and initial_leader
            in VALID_TEAMS
            and initial_leader
            != round_context.winner_team
        )

        initial_difference = (
            _alive_difference(
                t_alive=initial_t_alive,
                ct_alive=initial_ct_alive,
            )
        )

        max_t_advantage = max(
            0,
            initial_difference,
        )

        max_ct_advantage = max(
            0,
            -initial_difference,
        )

        for transition in (
            round_transitions
        ):
            before_leader = (
                _leading_team(
                    t_alive=(
                        transition
                        .t_alive_before
                    ),
                    ct_alive=(
                        transition
                        .ct_alive_before
                    ),
                )
            )

            after_leader = (
                _leading_team(
                    t_alive=(
                        transition
                        .t_alive_after
                    ),
                    ct_alive=(
                        transition
                        .ct_alive_after
                    ),
                )
            )

            after_difference = (
                _alive_difference(
                    t_alive=(
                        transition
                        .t_alive_after
                    ),
                    ct_alive=(
                        transition
                        .ct_alive_after
                    ),
                )
            )

            max_t_advantage = max(
                max_t_advantage,
                after_difference,
            )

            max_ct_advantage = max(
                max_ct_advantage,
                -after_difference,
            )

            if (
                round_context.winner_team
                in VALID_TEAMS
                and (
                    (
                        before_leader
                        in VALID_TEAMS
                        and before_leader
                        != round_context.winner_team
                    )
                    or (
                        after_leader
                        in VALID_TEAMS
                        and after_leader
                        != round_context.winner_team
                    )
                )
            ):
                winner_was_behind = (
                    True
                )

            if (
                first_advantage_team
                is None
                and before_leader
                is None
                and after_leader
                in VALID_TEAMS
            ):
                first_advantage_team = (
                    after_leader
                )

                first_advantage_tick = (
                    transition.tick
                )

                if (
                    transition.cause
                    == "enemy"
                    and transition
                    .attacker_team
                    == after_leader
                ):
                    first_advantage_by = (
                        transition.attacker
                    )

                continue

            if (
                first_advantage_team
                is None
            ):
                continue

            if (
                not first_team_has_lost
                and after_leader
                != first_advantage_team
            ):
                first_team_has_lost = (
                    True
                )

                advantage_lost = (
                    True
                )

                continue

            if (
                first_team_has_lost
                and after_leader
                == first_advantage_team
            ):
                advantage_restored = (
                    True
                )

        if (
            first_advantage_team
            is None
            or round_context.winner_team
            not in VALID_TEAMS
        ):
            converted = None

        else:
            converted = (
                round_context.winner_team
                == first_advantage_team
            )

        comeback_team = None

        if (
            winner_was_behind
            and round_context.winner_team
            in VALID_TEAMS
        ):
            comeback_team = (
                round_context.winner_team
            )

        summaries.append(
            RoundAdvantageSummary(
                round_num=(
                    round_context
                    .round_num
                ),
                winner_team=(
                    round_context
                    .winner_team
                ),
                first_advantage_team=(
                    first_advantage_team
                ),
                first_advantage_tick=(
                    first_advantage_tick
                ),
                first_advantage_by=(
                    first_advantage_by
                ),
                converted_first_advantage=(
                    converted
                ),
                advantage_lost=(
                    advantage_lost
                ),
                advantage_restored=(
                    advantage_restored
                ),
                comeback_team=(
                    comeback_team
                ),
                max_t_advantage=(
                    max_t_advantage
                ),
                max_ct_advantage=(
                    max_ct_advantage
                ),
            )
        )

    return summaries
