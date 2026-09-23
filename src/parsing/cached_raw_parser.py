from copy import deepcopy

from demoparser2 import DemoParser as RawDemoParser


class CachedRawDemoParser:
    """
    Thin cache layer over demoparser2.

    Only identical player_death parse_events calls are cached.
    All other parser calls are delegated unchanged.
    """

    def __init__(self, file_path: str):
        self._parser = RawDemoParser(file_path)
        self._player_death_events = None

    def parse_events(self, events, *args, **kwargs):
        is_plain_player_death = (
            list(events) == ["player_death"]
            and not args
            and not kwargs
        )

        if not is_plain_player_death:
            return self._parser.parse_events(
                events,
                *args,
                **kwargs,
            )

        if self._player_death_events is None:
            self._player_death_events = (
                self._parser.parse_events(
                    ["player_death"]
                )
            )

        # Keep the cached source immutable for consumers.
        return deepcopy(
            self._player_death_events
        )

    def __getattr__(self, name):
        return getattr(
            self._parser,
            name,
        )
