from __future__ import annotations

import unittest
from uuid import UUID

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import (
    get_auth_repository,
    get_presence_repository,
)
from src.auth.session import SESSION_COOKIE_NAME
from src.database.presence_repository import (
    PresenceSummary,
)


VISITOR_ID = (
    "123e4567-e89b-12d3-a456-426614174000"
)


class StubPresenceRepository:
    def __init__(self):
        self.touched: list[str] = []

    def touch(
        self,
        visitor_id: str,
    ) -> None:
        self.touched.append(
            visitor_id
        )

    def get_summary(
        self,
    ) -> PresenceSummary:
        return PresenceSummary(
            online=3,
            visitors_24h=17,
            logged_in_online=2,
        )


class StubAuthRepository:
    def __init__(self):
        self.resolved_tokens: list[str] = []

    def resolve_session(
        self,
        token: str,
    ):
        self.resolved_tokens.append(
            token
        )
        return None


class PresenceApiTest(unittest.TestCase):
    def setUp(self):
        self.presence = (
            StubPresenceRepository()
        )
        self.auth = (
            StubAuthRepository()
        )

        app.dependency_overrides[
            get_presence_repository
        ] = lambda: self.presence

        app.dependency_overrides[
            get_auth_repository
        ] = lambda: self.auth

        self.client = TestClient(
            app
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_summary_is_public(self):
        response = self.client.get(
            "/presence/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json(),
            {
                "online": 3,
                "visitors_24h": 17,
                "logged_in_online": 2,
            },
        )

    def test_heartbeat_touches_visitor(self):
        response = self.client.post(
            "/presence/heartbeat",
            json={
                "visitor_id": VISITOR_ID,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            self.presence.touched,
            [VISITOR_ID],
        )

        self.assertEqual(
            self.auth.resolved_tokens,
            [],
        )

    def test_heartbeat_refreshes_auth_session(
        self,
    ):
        self.client.cookies.set(
            SESSION_COOKIE_NAME,
            "test-session-token",
        )

        response = self.client.post(
            "/presence/heartbeat",
            json={
                "visitor_id": VISITOR_ID,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            self.auth.resolved_tokens,
            ["test-session-token"],
        )

    def test_heartbeat_rejects_bad_uuid(self):
        response = self.client.post(
            "/presence/heartbeat",
            json={
                "visitor_id": "not-a-uuid",
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )

        self.assertEqual(
            self.presence.touched,
            [],
        )


if __name__ == "__main__":
    unittest.main()
