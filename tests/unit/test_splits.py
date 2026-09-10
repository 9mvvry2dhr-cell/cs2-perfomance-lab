import unittest

import pandas as pd

from src.metrics.splits import (
    calculate_split_metrics,
    detect_player_round_damage,
    detect_player_round_sides,
)


class FakeDemoParser:
    def __init__(
        self,
        team_rows,
        starts=None,
        freezes=None,
        ends=None,
        panel_ticks=None,
        deaths=None,
        damage_rows=None,
    ):
        self.team_rows = team_rows

        self.starts = (
            starts
            if starts is not None
            else [100]
        )

        self.freezes = (
            freezes
            if freezes is not None
            else [150]
        )

        self.ends = (
            ends
            if ends is not None
            else [
                {
                    "tick": 900,
                    "winner": "CT",
                }
            ]
        )

        self.panel_ticks = (
            panel_ticks
            if panel_ticks is not None
            else []
        )

        self.deaths = (
            deaths
            if deaths is not None
            else []
        )

        self.damage_rows = (
            damage_rows
            if damage_rows is not None
            else []
        )

    def parse_events(
        self,
        event_names,
    ):
        event_name = event_names[0]

        if event_name == "round_start":
            return pd.DataFrame(
                {"tick": self.starts}
            )

        if event_name == "round_freeze_end":
            return pd.DataFrame(
                {"tick": self.freezes}
            )

        if event_name == "round_end":
            return pd.DataFrame(
                self.ends
            )

        if event_name == "cs_win_panel_match":
            return pd.DataFrame(
                {"tick": self.panel_ticks}
            )

        if event_name == "player_death":
            return pd.DataFrame(
                self.deaths
            )

        return pd.DataFrame()

    def parse_ticks(
        self,
        fields,
        ticks=None,
    ):
        wanted_ticks = set(
            ticks or []
        )

        source_rows = (
            self.damage_rows
            if "damage_total" in fields
            else self.team_rows
        )

        return pd.DataFrame([
            row
            for row in source_rows
            if row["tick"] in wanted_ticks
        ])


class TestPlayerRoundSides(unittest.TestCase):

    def test_single_round_t_side(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
            ],
        )

        events = detect_player_round_sides(
            parser,
            ["A"],
        )

        self.assertEqual(
            len(events),
            1,
        )

        self.assertEqual(
            events[0].round_num,
            1,
        )

        self.assertEqual(
            events[0].steam_id,
            "A",
        )

        self.assertEqual(
            events[0].side,
            "T",
        )

    def test_halftime_side_change(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
            ],
            starts=[
                100,
                1000,
            ],
            freezes=[
                150,
                1050,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
            ],
        )

        events = detect_player_round_sides(
            parser,
            ["A"],
        )

        self.assertEqual(
            [
                (event.round_num, event.side)
                for event in events
            ],
            [
                (1, "T"),
                (2, "CT"),
            ],
        )

    def test_repeated_side_changes_are_supported(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1950,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 2850,
                    "steamid": "A",
                    "team_num": 3,
                },
            ],
            starts=[
                100,
                1000,
                1900,
                2800,
            ],
            freezes=[
                150,
                1050,
                1950,
                2850,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
                {
                    "tick": 2700,
                    "winner": "CT",
                },
                {
                    "tick": 3600,
                    "winner": "T",
                },
            ],
        )

        events = detect_player_round_sides(
            parser,
            ["A"],
        )

        self.assertEqual(
            [
                (event.round_num, event.side)
                for event in events
            ],
            [
                (1, "T"),
                (2, "CT"),
                (3, "T"),
                (4, "CT"),
            ],
        )

    def test_invalid_team_num_is_ignored(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 1,
                },
            ],
        )

        events = detect_player_round_sides(
            parser,
            ["A"],
        )

        self.assertEqual(
            events,
            [],
        )

    def test_player_not_in_requested_ids_is_ignored(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },
            ],
        )

        events = detect_player_round_sides(
            parser,
            ["A"],
        )

        self.assertEqual(
            len(events),
            1,
        )

        self.assertEqual(
            events[0].steam_id,
            "A",
        )


class TestSplitMetrics(unittest.TestCase):

    def test_rounds_and_survival_follow_side_change(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
            ],
            starts=[
                100,
                1000,
            ],
            freezes=[
                150,
                1050,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["T"]["rounds_played"],
            1,
        )
        self.assertEqual(
            stats["A"]["CT"]["rounds_played"],
            1,
        )
        self.assertEqual(
            stats["A"]["T"]["survived_rounds"],
            1,
        )
        self.assertEqual(
            stats["A"]["CT"]["survived_rounds"],
            1,
        )

    def test_enemy_kills_follow_attacker_side(self):
        parser = FakeDemoParser(
            team_rows=[
                # Round 1 freeze_end
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },

                # Round 1 death tick
                {
                    "tick": 500,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 500,
                    "steamid": "B",
                    "team_num": 3,
                },

                # Round 2 freeze_end
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1050,
                    "steamid": "B",
                    "team_num": 2,
                },

                # Round 2 death tick
                {
                    "tick": 1400,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1400,
                    "steamid": "B",
                    "team_num": 2,
                },
            ],
            starts=[
                100,
                1000,
            ],
            freezes=[
                150,
                1050,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "T",
                },
                {
                    "tick": 1800,
                    "winner": "CT",
                },
            ],
            deaths=[
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
                {
                    "tick": 1400,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A", "B"],
        )

        self.assertEqual(
            stats["A"]["T"]["kills"],
            1,
        )
        self.assertEqual(
            stats["A"]["CT"]["kills"],
            1,
        )

        self.assertEqual(
            stats["B"]["CT"]["deaths"],
            1,
        )
        self.assertEqual(
            stats["B"]["T"]["deaths"],
            1,
        )

    def test_teamkill_counts_death_but_not_kill(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 2,
                },
                {
                    "tick": 500,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 500,
                    "steamid": "B",
                    "team_num": 2,
                },
            ],
            deaths=[
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A", "B"],
        )

        self.assertEqual(
            stats["A"]["T"]["kills"],
            0,
        )
        self.assertEqual(
            stats["B"]["T"]["deaths"],
            1,
        )
        self.assertEqual(
            stats["B"]["T"]["survived_rounds"],
            0,
        )

    def test_suicide_counts_death_but_not_kill(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 500,
                    "steamid": "A",
                    "team_num": 3,
                },
            ],
            deaths=[
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "A",
                },
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["CT"]["kills"],
            0,
        )
        self.assertEqual(
            stats["A"]["CT"]["deaths"],
            1,
        )
        self.assertEqual(
            stats["A"]["CT"]["survived_rounds"],
            0,
        )

    def test_unknown_relation_does_not_create_kill(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "B",
                    "team_num": 3,
                },

                # Only attacker team is known at death tick.
                {
                    "tick": 500,
                    "steamid": "A",
                    "team_num": 2,
                },
            ],
            deaths=[
                {
                    "tick": 500,
                    "attacker_steamid": "A",
                    "user_steamid": "B",
                },
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A", "B"],
        )

        self.assertEqual(
            stats["A"]["T"]["kills"],
            0,
        )

        # Victim death still belongs to the victim's verified
        # round side from freeze_end.
        self.assertEqual(
            stats["B"]["CT"]["deaths"],
            1,
        )




    def test_kast_rounds_follow_player_side(self):
        parser = FakeDemoParser(
            team_rows=[
                # Round 1: A is T.
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 150,
                    "steamid": "X",
                    "team_num": 3,
                },
                {
                    "tick": 150,
                    "steamid": "Y",
                    "team_num": 3,
                },

                # Round 1 kill.
                {
                    "tick": 300,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 300,
                    "steamid": "X",
                    "team_num": 3,
                },

                # Round 1 A dies.
                {
                    "tick": 600,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 600,
                    "steamid": "Y",
                    "team_num": 3,
                },

                # Round 2: A is now CT.
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1050,
                    "steamid": "Z",
                    "team_num": 2,
                },

                # Round 2 A dies without K/A/S/T.
                {
                    "tick": 1400,
                    "steamid": "A",
                    "team_num": 3,
                },
                {
                    "tick": 1400,
                    "steamid": "Z",
                    "team_num": 2,
                },
            ],
            starts=[
                100,
                1000,
            ],
            freezes=[
                150,
                1050,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
            ],
            deaths=[
                {
                    "tick": 300,
                    "game_time": 10.0,
                    "attacker_steamid": "A",
                    "user_steamid": "X",
                    "assister_steamid": "",
                },
                {
                    "tick": 600,
                    "game_time": 20.0,
                    "attacker_steamid": "Y",
                    "user_steamid": "A",
                    "assister_steamid": "",
                },
                {
                    "tick": 1400,
                    "game_time": 40.0,
                    "attacker_steamid": "Z",
                    "user_steamid": "A",
                    "assister_steamid": "",
                },
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A", "X", "Y", "Z"],
        )

        self.assertEqual(
            stats["A"]["T"]["kast_rounds"],
            1,
        )

        self.assertEqual(
            stats["A"]["CT"]["kast_rounds"],
            0,
        )

        self.assertEqual(
            stats["A"]["T"]["rounds_played"],
            1,
        )

        self.assertEqual(
            stats["A"]["CT"]["rounds_played"],
            1,
        )


    def test_damage_deltas_follow_player_side(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 3,
                },
            ],
            starts=[
                100,
                1000,
            ],
            freezes=[
                150,
                1050,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "T",
                },
                {
                    "tick": 1800,
                    "winner": "CT",
                },
            ],
            damage_rows=[
                {
                    "tick": 900,
                    "steamid": "A",
                    "damage_total": 120,
                },
                {
                    "tick": 1800,
                    "steamid": "A",
                    "damage_total": 190,
                },
            ],
        )

        events = detect_player_round_damage(
            parser,
            ["A"],
        )

        self.assertEqual(
            [
                (
                    event.round_num,
                    event.damage,
                )
                for event in events
            ],
            [
                (1, 120.0),
                (2, 70.0),
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["T"]["damage"],
            120.0,
        )

        self.assertEqual(
            stats["A"]["CT"]["damage"],
            70.0,
        )

    def test_missing_damage_snapshot_breaks_continuity(self):
        parser = FakeDemoParser(
            team_rows=[],
            starts=[
                100,
                1000,
                1900,
                2800,
            ],
            freezes=[
                150,
                1050,
                1950,
                2850,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
                {
                    "tick": 2700,
                    "winner": "CT",
                },
                {
                    "tick": 3600,
                    "winner": "T",
                },
            ],
            damage_rows=[
                {
                    "tick": 900,
                    "steamid": "A",
                    "damage_total": 100,
                },
                # Round 2 snapshot intentionally missing.
                {
                    "tick": 2700,
                    "steamid": "A",
                    "damage_total": 250,
                },
                {
                    "tick": 3600,
                    "steamid": "A",
                    "damage_total": 300,
                },
            ],
        )

        events = detect_player_round_damage(
            parser,
            ["A"],
        )

        self.assertEqual(
            [
                (
                    event.round_num,
                    event.damage,
                )
                for event in events
            ],
            [
                (1, 100.0),
                (4, 50.0),
            ],
        )

    def test_damage_counter_reset_does_not_create_negative_damage(self):
        parser = FakeDemoParser(
            team_rows=[],
            starts=[
                100,
                1000,
                1900,
            ],
            freezes=[
                150,
                1050,
                1950,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "CT",
                },
                {
                    "tick": 1800,
                    "winner": "T",
                },
                {
                    "tick": 2700,
                    "winner": "CT",
                },
            ],
            damage_rows=[
                {
                    "tick": 900,
                    "steamid": "A",
                    "damage_total": 100,
                },
                {
                    "tick": 1800,
                    "steamid": "A",
                    "damage_total": 20,
                },
                {
                    "tick": 2700,
                    "steamid": "A",
                    "damage_total": 70,
                },
            ],
        )

        events = detect_player_round_damage(
            parser,
            ["A"],
        )

        self.assertEqual(
            [
                (
                    event.round_num,
                    event.damage,
                )
                for event in events
            ],
            [
                (1, 100.0),
                (3, 50.0),
            ],
        )


    def test_partial_player_participation_counts_only_verified_rounds(self):
        parser = FakeDemoParser(
            team_rows=[
                {
                    "tick": 150,
                    "steamid": "A",
                    "team_num": 2,
                },
                {
                    "tick": 1050,
                    "steamid": "A",
                    "team_num": 2,
                },
                # A is absent from round 3 freeze_end roster.
            ],
            starts=[
                100,
                1000,
                1900,
            ],
            freezes=[
                150,
                1050,
                1950,
            ],
            ends=[
                {
                    "tick": 900,
                    "winner": "T",
                },
                {
                    "tick": 1800,
                    "winner": "CT",
                },
                {
                    "tick": 2700,
                    "winner": "CT",
                },
            ],
        )

        stats = calculate_split_metrics(
            parser,
            ["A"],
        )

        self.assertEqual(
            stats["A"]["T"]["rounds_played"],
            2,
        )

        self.assertEqual(
            stats["A"]["CT"]["rounds_played"],
            0,
        )

        self.assertEqual(
            (
                stats["A"]["T"]["rounds_played"]
                + stats["A"]["CT"]["rounds_played"]
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
