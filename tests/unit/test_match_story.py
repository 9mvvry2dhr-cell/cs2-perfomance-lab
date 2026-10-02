import unittest

from src.metrics.entry import EntryEvent
from src.metrics.match_story import (
    select_match_story_events,
)
from src.metrics.multikill import MultikillRound
from src.metrics.trade import TradeEvent


PLAYER = "76561198000000001"
ENEMY = "76561198000000002"
TEAMMATE = "76561198000000003"


def trade_event(
    *,
    round_num: int,
    victim: str,
    trader: str,
    original_killer: str,
) -> TradeEvent:
    return TradeEvent(
        round_num=round_num,
        victim=victim,
        trader=trader,
        original_killer=original_killer,
        death_tick=100,
        retaliation_tick=110,
        death_game_time=10.0,
        retaliation_game_time=11.0,
        retaliation_event_order=1,
    )


class MatchStoryTests(unittest.TestCase):

    def test_three_k_entry_becomes_highlight(self):
        result = select_match_story_events(
            [PLAYER],
            entry_events=[
                EntryEvent(
                    round_num=8,
                    attacker=PLAYER,
                    victim=ENEMY,
                    tick=100,
                ),
            ],
            trade_events=[],
            multikill_rounds=[
                MultikillRound(
                    round_num=8,
                    steam_id=PLAYER,
                    kills=3,
                ),
            ],
        )

        events = result[PLAYER]

        self.assertEqual(
            len(events),
            1,
        )

        event = events[0]

        self.assertEqual(
            event.event_type,
            "highlight",
        )
        self.assertEqual(
            event.round_num,
            8,
        )
        self.assertEqual(
            event.evidence["kills"],
            3,
        )
        self.assertTrue(
            event.evidence["entry_kill"]
        )


    def test_entry_death_without_trade_becomes_growth(self):
        result = select_match_story_events(
            [PLAYER],
            entry_events=[
                EntryEvent(
                    round_num=14,
                    attacker=ENEMY,
                    victim=PLAYER,
                    tick=100,
                ),
            ],
            trade_events=[],
            multikill_rounds=[],
        )

        events = result[PLAYER]

        self.assertEqual(
            len(events),
            1,
        )

        event = events[0]

        self.assertEqual(
            event.event_type,
            "growth",
        )
        self.assertEqual(
            event.round_num,
            14,
        )
        self.assertTrue(
            event.evidence["entry_death"]
        )
        self.assertFalse(
            event.evidence["was_traded"]
        )


    def test_traded_entry_death_has_lower_growth_score(self):
        result = select_match_story_events(
            [PLAYER],
            entry_events=[
                EntryEvent(
                    round_num=5,
                    attacker=ENEMY,
                    victim=PLAYER,
                    tick=100,
                ),
                EntryEvent(
                    round_num=6,
                    attacker=ENEMY,
                    victim=PLAYER,
                    tick=200,
                ),
            ],
            trade_events=[
                trade_event(
                    round_num=5,
                    victim=PLAYER,
                    trader=TEAMMATE,
                    original_killer=ENEMY,
                ),
            ],
            multikill_rounds=[],
        )

        event = result[PLAYER][0]

        self.assertEqual(
            event.event_type,
            "growth",
        )

        # Раунд 6 должен быть выбран:
        # там entry death осталась без размена.
        self.assertEqual(
            event.round_num,
            6,
        )
        self.assertFalse(
            event.evidence["was_traded"]
        )


    def test_two_k_with_trade_becomes_highlight(self):
        result = select_match_story_events(
            [PLAYER],
            entry_events=[],
            trade_events=[
                trade_event(
                    round_num=10,
                    victim=TEAMMATE,
                    trader=PLAYER,
                    original_killer=ENEMY,
                ),
            ],
            multikill_rounds=[
                MultikillRound(
                    round_num=10,
                    steam_id=PLAYER,
                    kills=2,
                ),
            ],
        )

        event = result[PLAYER][0]

        self.assertEqual(
            event.event_type,
            "highlight",
        )
        self.assertEqual(
            event.round_num,
            10,
        )
        self.assertEqual(
            event.evidence["kills"],
            2,
        )
        self.assertEqual(
            event.evidence["trades_made"],
            1,
        )


    def test_key_event_uses_different_round_than_highlight(self):
        result = select_match_story_events(
            [PLAYER],
            entry_events=[
                EntryEvent(
                    round_num=3,
                    attacker=PLAYER,
                    victim=ENEMY,
                    tick=100,
                ),
                EntryEvent(
                    round_num=9,
                    attacker=PLAYER,
                    victim=ENEMY,
                    tick=200,
                ),
            ],
            trade_events=[
                trade_event(
                    round_num=9,
                    victim=TEAMMATE,
                    trader=PLAYER,
                    original_killer=ENEMY,
                ),
            ],
            multikill_rounds=[
                MultikillRound(
                    round_num=3,
                    steam_id=PLAYER,
                    kills=3,
                ),
                MultikillRound(
                    round_num=9,
                    steam_id=PLAYER,
                    kills=2,
                ),
            ],
        )

        events = result[PLAYER]

        self.assertEqual(
            [event.event_type for event in events],
            [
                "highlight",
                "key",
            ],
        )

        self.assertEqual(
            events[0].round_num,
            3,
        )
        self.assertEqual(
            events[1].round_num,
            9,
        )


    def test_weak_rounds_do_not_create_story(self):
        result = select_match_story_events(
            [PLAYER],
            entry_events=[],
            trade_events=[],
            multikill_rounds=[
                MultikillRound(
                    round_num=4,
                    steam_id=PLAYER,
                    kills=2,
                ),
            ],
        )

        self.assertEqual(
            result[PLAYER],
            [],
        )


if __name__ == "__main__":
    unittest.main()
