from src.parsing import cached_raw_parser as module


class FakeRawParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.parse_events_calls = []
        self.parse_event_calls = []

    def parse_events(self, events, *args, **kwargs):
        self.parse_events_calls.append(
            (tuple(events), args, kwargs)
        )
        return {
            "events": [
                {"tick": 123}
            ]
        }

    def parse_event(self, event, *args, **kwargs):
        self.parse_event_calls.append(
            (event, args, kwargs)
        )
        return "delegated"


def test_player_death_is_cached_and_isolated(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "RawDemoParser",
        FakeRawParser,
    )

    parser = module.CachedRawDemoParser(
        "demo.dem"
    )

    first = parser.parse_events(
        ["player_death"]
    )

    first["events"][0]["tick"] = 999

    second = parser.parse_events(
        ["player_death"]
    )

    assert len(
        parser._parser.parse_events_calls
    ) == 1

    assert second == {
        "events": [
            {"tick": 123}
        ]
    }


def test_other_events_are_not_cached(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "RawDemoParser",
        FakeRawParser,
    )

    parser = module.CachedRawDemoParser(
        "demo.dem"
    )

    parser.parse_events(["round_end"])
    parser.parse_events(["round_end"])

    assert len(
        parser._parser.parse_events_calls
    ) == 2


def test_parse_event_is_delegated(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "RawDemoParser",
        FakeRawParser,
    )

    parser = module.CachedRawDemoParser(
        "demo.dem"
    )

    result = parser.parse_event(
        "player_death",
        other=["game_time"],
    )

    assert result == "delegated"

    assert len(
        parser._parser.parse_event_calls
    ) == 1
