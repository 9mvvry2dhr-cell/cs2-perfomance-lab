import unittest
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.app import app
from src.api.dependencies import (
    get_analysis_repository,
    get_current_user,
    get_database_session,
)
from src.api.schemas import (
    MatchAnalysisResponse,
    PlayerHistorySummaryResponse,
    PlayerMatchHistoryResponse,
)
from src.domain.identity import CurrentUser
from src.domain.history import (
    PlayerMatchHistoryItem,
    build_player_history_summary,
)
from tests.unit.test_analysis_repository import make_analysis


class StubAnalysisRepository:
    def __init__(
        self,
        analysis=None,
        error=None,
        history=None,
        summary=None,
        user_match_position=0,
    ):
        self.analysis = analysis
        self.error = error
        self.user_match_position = (
            user_match_position
        )
        self.history = (
            history
            if history is not None
            else []
        )
        self.summary = summary

    def get_analysis(
        self,
        match_id: str,
    ):
        if self.error is not None:
            raise self.error

        if (
            self.analysis is not None
            and self.analysis.match_id == match_id
        ):
            return self.analysis

        return None

    def get_user_match_position(
        self,
        *,
        owner_steam_id: str,
        match_id: str,
    ):
        if self.error is not None:
            raise self.error

        return self.user_match_position

    def get_player_match_history(
        self,
        steam_id: str,
        *,
        limit: int = 20,
        owner_steam_id: str | None = None,
    ):
        if self.error is not None:
            raise self.error

        return self.history[:limit]

    def get_player_history_summary(
        self,
        steam_id: str,
        *,
        limit: int = 10,
        owner_steam_id: str | None = None,
    ):
        if self.error is not None:
            raise self.error

        return self.summary


class StubSession:
    def execute(self, _):
        return None


class ApiTest(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[
            get_current_user
        ] = lambda: CurrentUser(
            steam_id=(
                "76561198055629469"
            )
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_returns_ok(self):
        client = TestClient(app)

        response = client.get(
            "/health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.json(),
            {"status": "ok"},
        )

    def test_ready_returns_ready(self):
        app.dependency_overrides[
            get_database_session
        ] = lambda: StubSession()

        client = TestClient(app)

        response = client.get(
            "/ready"
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.json(),
            {"status": "ready"},
        )

    def test_get_match_returns_analysis(self):
        expected = make_analysis()

        repository = StubAnalysisRepository(
            analysis=expected
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            f"/matches/{expected.match_id}"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        expected_json = (
            MatchAnalysisResponse
            .model_validate(expected)
            .model_dump(mode="json")
        )

        self.assertEqual(
            response.json(),
            expected_json,
        )

    def test_get_match_returns_404_when_missing(self):
        repository = StubAnalysisRepository()

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/matches/missing-match"
        )

        self.assertEqual(
            response.status_code,
            404,
        )
        self.assertEqual(
            response.json(),
            {
                "detail": "Match not found",
            },
        )

    def test_database_error_returns_503(self):
        repository = StubAnalysisRepository(
            error=SQLAlchemyError(
                "simulated database failure"
            )
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/matches/test-match"
        )

        self.assertEqual(
            response.status_code,
            503,
        )
        self.assertEqual(
            response.json(),
            {
                "detail": "Database unavailable",
            },
        )


    def _history_item(self):
        analysis = make_analysis()

        player = analysis.players[0]

        return PlayerMatchHistoryItem(
            match_id=analysis.match_id,
            analyzed_at=datetime(
                2026,
                9,
                18,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            map_name=analysis.map_name,
            score_ct=analysis.score_ct,
            score_t=analysis.score_t,
            player_name=player.name,
            stats=player.stats,
            findings=player.findings,
            sides=player.sides,
            player_result="win",
        )


    def test_get_player_matches_returns_history(self):
        item = replace(
            self._history_item(),
            player_name="Player 1",
        )

        repository = StubAnalysisRepository(
            history=[
                item
            ]
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        with patch(
            "src.api.app.fetch_steam_profile",
            return_value=SimpleNamespace(
                player_name="live-steam-name",
            ),
        ):
            response = client.get(
                "/players/76561198055629469/matches"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        expected_item = replace(
            item,
            player_name="live-steam-name",
        )

        expected = [
            (
                PlayerMatchHistoryResponse
                .model_validate(expected_item)
                .model_dump(mode="json")
            )
        ]

        self.assertEqual(
            response.json(),
            expected,
        )

        self.assertEqual(
            response.json()[0]["sides"]["CT"]["adr"],
            123.5,
        )

        self.assertEqual(
            response.json()[0]["sides"]["T"]["entry_deaths"],
            1,
        )


    def test_get_player_matches_rejects_other_player(self):
        repository = StubAnalysisRepository(
            history=[]
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/players/other-player/matches"
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Access to another player "
                    "is forbidden"
                ),
            },
        )


    def test_get_player_summary_returns_summary(self):
        item = replace(
            self._history_item(),
            player_name="Player 1",
        )

        summary = build_player_history_summary(
            "76561198055629469",
            [
                item
            ],
        )

        repository = StubAnalysisRepository(
            summary=summary
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        with patch(
            "src.api.app.fetch_steam_profile",
            return_value=SimpleNamespace(
                player_name="live-steam-name",
            ),
        ):
            response = client.get(
                "/players/76561198055629469/summary"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        expected_summary = replace(
            summary,
            steam_id="76561198055629469",
            player_name="live-steam-name",
        )

        expected = (
            PlayerHistorySummaryResponse
            .model_validate(expected_summary)
            .model_dump(mode="json")
        )

        self.assertEqual(
            response.json(),
            expected,
        )


    def test_get_player_summary_returns_404_when_missing(self):
        repository = StubAnalysisRepository(
            summary=None
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/players/76561198055629469/summary"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Player history not found"
                ),
            },
        )


    def test_player_history_limit_is_validated(self):
        repository = StubAnalysisRepository()

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        for endpoint in (
            "matches",
            "summary",
        ):
            for limit in (
                0,
                101,
            ):
                with self.subTest(
                    endpoint=endpoint,
                    limit=limit,
                ):
                    response = client.get(
                        (
                            "/players/123/"
                            f"{endpoint}"
                            f"?limit={limit}"
                        )
                    )

                    self.assertEqual(
                        response.status_code,
                        422,
                    )


    def test_get_me_returns_authenticated_identity(self):
        client = TestClient(app)

        response = client.get(
            "/me"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json(),
            {
                "steam_id": (
                    "76561198055629469"
                ),
                "player_name": None,
                "avatar_url": None,
            },
        )


    def test_match_response_uses_user_match_position(self):
        expected = make_analysis()

        linked_player = replace(
            expected.players[0],
            steam_id="anon:0",
            name="Player 1",
        )

        analysis = replace(
            expected,
            players=[
                linked_player,
                expected.players[0],
            ],
        )

        repository = StubAnalysisRepository(
            analysis=analysis,
            user_match_position=0,
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        with patch(
            "src.api.app.fetch_steam_profile",
            return_value=SimpleNamespace(
                player_name="live-steam-name",
            ),
        ):
            response = client.get(
                f"/matches/{analysis.match_id}"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        players = response.json()[
            "players"
        ]

        self.assertEqual(
            len(players),
            1,
        )

        self.assertEqual(
            players[0]["steam_id"],
            "76561198055629469",
        )

        self.assertEqual(
            players[0]["name"],
            "live-steam-name",
        )


    def test_match_is_hidden_without_user_match_link(self):
        analysis = make_analysis()

        repository = StubAnalysisRepository(
            analysis=analysis,
            user_match_position=None,
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            f"/matches/{analysis.match_id}"
        )

        self.assertEqual(
            response.status_code,
            404,
        )


    def test_get_my_matches_uses_authenticated_player(self):
        item = self._history_item()

        repository = StubAnalysisRepository(
            history=[
                item
            ]
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/me/matches"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            len(response.json()),
            1,
        )


    def test_get_my_summary_uses_authenticated_player(self):
        item = self._history_item()

        summary = build_player_history_summary(
            "76561198055629469",
            [
                item
            ],
        )

        repository = StubAnalysisRepository(
            summary=summary
        )

        app.dependency_overrides[
            get_analysis_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.get(
            "/me/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json()[
                "steam_id"
            ],
            "76561198055629469",
        )


if __name__ == "__main__":
    unittest.main()
