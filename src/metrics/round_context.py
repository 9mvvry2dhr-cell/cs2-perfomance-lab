from dataclasses import dataclass
from typing import List, Optional

from demoparser2 import DemoParser as RawDemoParser


@dataclass(frozen=True)
class RoundContext:
    """
    Каноническое описание одного сыгранного раунда.
    """

    round_num: int
    start_tick: int
    freeze_end_tick: int
    end_tick: int
    winner_team: Optional[int]


def build_round_contexts(
    raw_parser: RawDemoParser
) -> List[RoundContext]:
    """
    Строит подтверждённые сыгранные раунды.

    Правила:

    - нет хардкода на 24 раунда;
    - учитываются только CT/T round_end;
    - лишние round_start не ломают сопоставление;
    - для каждого round_end берём последний round_start
      после предыдущего round_end;
    - freeze_end используется как snapshot начала live-play;
    - события после cs_win_panel_match отбрасываются,
      если событие доступно.
    """

    try:
        start_events = raw_parser.parse_events(
            ["round_start"]
        )

        freeze_events = raw_parser.parse_events(
            ["round_freeze_end"]
        )

        end_events = raw_parser.parse_events(
            ["round_end"]
        )

        df_start = extract_dataframe(
            start_events
        )

        df_freeze = extract_dataframe(
            freeze_events
        )

        df_end = extract_dataframe(
            end_events
        )

    except Exception:
        return []

    if (
        df_start is None
        or df_start.empty
        or "tick" not in df_start.columns
    ):
        return []

    if (
        df_end is None
        or df_end.empty
        or "tick" not in df_end.columns
    ):
        return []

    df_end = df_end.copy()

    # --------------------------------------------------------------
    # Только реальные CT/T round_end.
    # --------------------------------------------------------------

    if "winner" in df_end.columns:
        df_end = df_end[
            df_end["winner"].apply(
                lambda value:
                normalize_team_num(value)
                is not None
            )
        ].copy()

    # --------------------------------------------------------------
    # Официальный конец матча.
    # --------------------------------------------------------------

    try:
        panel_events = raw_parser.parse_events(
            ["cs_win_panel_match"]
        )

        df_panel = extract_dataframe(
            panel_events
        )

        if (
            df_panel is not None
            and not df_panel.empty
            and "tick" in df_panel.columns
        ):
            match_end_tick = safe_int(
                df_panel["tick"].max(),
                default=-1
            )

            if match_end_tick >= 0:
                df_end = df_end[
                    df_end["tick"]
                    <= match_end_tick
                ].copy()

    except Exception:
        pass

    df_end = (
        df_end
        .sort_values("tick")
        .reset_index(drop=True)
    )

    start_ticks = sorted(
        df_start["tick"]
        .dropna()
        .astype(int)
        .tolist()
    )

    freeze_ticks = []

    if (
        df_freeze is not None
        and not df_freeze.empty
        and "tick" in df_freeze.columns
    ):
        freeze_ticks = sorted(
            df_freeze["tick"]
            .dropna()
            .astype(int)
            .tolist()
        )

    if (
        not start_ticks
        or df_end.empty
    ):
        return []

    contexts: List[RoundContext] = []

    previous_end = -1

    for _, row in df_end.iterrows():

        end_tick = safe_int(
            row.get("tick"),
            default=-1
        )

        if end_tick < 0:
            continue

        possible_starts = [
            tick
            for tick in start_ticks
            if (
                previous_end
                < tick
                <= end_tick
            )
        ]

        if not possible_starts:
            previous_end = end_tick
            continue

        # Если между двумя round_end оказалось несколько
        # round_start, берём последний.
        start_tick = max(
            possible_starts
        )

        possible_freezes = [
            tick
            for tick in freeze_ticks
            if (
                start_tick
                <= tick
                <= end_tick
            )
        ]

        freeze_end_tick = (
            min(possible_freezes)
            if possible_freezes
            else start_tick
        )

        contexts.append(
            RoundContext(
                round_num=len(contexts) + 1,
                start_tick=start_tick,
                freeze_end_tick=freeze_end_tick,
                end_tick=end_tick,
                winner_team=normalize_team_num(
                    row.get("winner")
                ),
            )
        )

        previous_end = end_tick

    return contexts


def find_round(
    tick,
    rounds: List[RoundContext]
) -> Optional[RoundContext]:
    """
    Возвращает раунд, которому принадлежит tick.
    """

    tick = safe_int(
        tick,
        default=-1
    )

    for round_context in rounds:
        if (
            round_context.start_tick
            <= tick
            <= round_context.end_tick
        ):
            return round_context

    return None


def extract_dataframe(events):
    """
    Нормализует возможные формы ответа demoparser2.
    """

    if events is None:
        return None

    if hasattr(events, "iterrows"):
        return events

    if (
        isinstance(events, list)
        and events
    ):
        first = events[0]

        if (
            isinstance(first, tuple)
            and len(first) >= 2
        ):
            return first[1]

        return first

    return None


def valid_sid(value) -> bool:
    steam_id = str(
        value
    )

    return steam_id not in {
        "",
        "0",
        "None",
        "nan",
        "NaN",
    }


def normalize_team_num(value) -> Optional[int]:
    """
    Source team_num:
        T  = 2
        CT = 3
    """

    if value is None:
        return None

    normalized = str(
        value
    ).strip().upper()

    if normalized in {
        "T",
        "2",
        "TERRORIST",
        "TERRORISTS",
    }:
        return 2

    if normalized in {
        "CT",
        "3",
        "COUNTER-TERRORIST",
        "COUNTER_TERRORIST",
    }:
        return 3

    return None


def safe_int(
    value,
    default=0
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def safe_float(
    value,
    default=0.0
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default