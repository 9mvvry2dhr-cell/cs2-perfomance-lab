from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.app import app
from src.api.dependencies import (
    get_current_user,
    get_database_session,
)
from src.database.models import (
    Base,
    FoundingTesterModel,
)


ADMIN_STEAM_ID = "76561198000000001"
OTHER_STEAM_ID = "76561198000000002"
TESTER_STEAM_ID = "76561198073935652"


class FoundingTesterAdminApiTest(
    unittest.TestCase
):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={
                "check_same_thread": False,
            },
            poolclass=StaticPool,
        )

        Base.metadata.create_all(
            self.engine
        )

        self.session = Session(
            self.engine
        )

        for number in range(1, 11):
            self.session.add(
                FoundingTesterModel(
                    number=number,
                    premium_days=30,
                )
            )

        slot = self.session.get(
            FoundingTesterModel,
            1,
        )

        slot.steam_id = (
            TESTER_STEAM_ID
        )

        slot.awarded_at = datetime(
            2026,
            10,
            2,
            6,
            45,
            39,
            tzinfo=timezone.utc,
        )

        self.session.commit()

        app.dependency_overrides[
            get_database_session
        ] = lambda: self.session

        self.client = TestClient(
            app
        )

    def tearDown(self):
        app.dependency_overrides.clear()

        self.session.close()
        self.engine.dispose()

    def test_requires_authentication(
        self,
    ):
        def unauthorized():
            raise HTTPException(
                status_code=401,
                detail=(
                    "Authentication required"
                ),
            )

        app.dependency_overrides[
            get_current_user
        ] = unauthorized

        with patch.dict(
            os.environ,
            {
                "ADMIN_STEAM_ID":
                    ADMIN_STEAM_ID,
            },
        ):
            response = self.client.get(
                "/admin/founding-testers"
            )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_rejects_non_admin(
        self,
    ):
        app.dependency_overrides[
            get_current_user
        ] = lambda: SimpleNamespace(
            steam_id=OTHER_STEAM_ID
        )

        with patch.dict(
            os.environ,
            {
                "ADMIN_STEAM_ID":
                    ADMIN_STEAM_ID,
            },
        ):
            response = self.client.get(
                "/admin/founding-testers"
            )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            response.json(),
            {
                "detail":
                    "Admin access required",
            },
        )

    def test_admin_gets_founding_testers(
        self,
    ):
        app.dependency_overrides[
            get_current_user
        ] = lambda: SimpleNamespace(
            steam_id=ADMIN_STEAM_ID
        )

        with patch.dict(
            os.environ,
            {
                "ADMIN_STEAM_ID":
                    ADMIN_STEAM_ID,
            },
        ):
            response = self.client.get(
                "/admin/founding-testers"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["total"],
            10,
        )

        self.assertEqual(
            body["claimed"],
            1,
        )

        self.assertEqual(
            body["remaining"],
            9,
        )

        self.assertEqual(
            len(body["testers"]),
            1,
        )

        tester = body["testers"][0]

        self.assertEqual(
            tester["number"],
            1,
        )

        self.assertEqual(
            tester["steam_id"],
            TESTER_STEAM_ID,
        )

        self.assertEqual(
            tester["premium_days"],
            30,
        )

        self.assertTrue(
            tester["awarded_at"]
        )


if __name__ == "__main__":
    unittest.main()
