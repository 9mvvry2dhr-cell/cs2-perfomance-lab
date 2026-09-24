import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import (
    get_bug_report_repository,
    get_current_user,
)
from src.database.bug_report_repository import (
    BugReportReferenceError,
)
from src.domain.bug_reports import BugReport
from src.domain.identity import CurrentUser


class StubBugReportRepository:
    def __init__(
        self,
        *,
        error=None,
    ):
        self.error = error
        self.last_call = None

    def create_report(
        self,
        *,
        owner_steam_id,
        category,
        message,
        match_id=None,
        job_id=None,
    ):
        self.last_call = {
            "owner_steam_id":
                owner_steam_id,
            "category": category,
            "message": message,
            "match_id": match_id,
            "job_id": job_id,
        }

        if self.error is not None:
            raise self.error

        return BugReport(
            id="report-001",
            owner_steam_id=(
                owner_steam_id
            ),
            category=category,
            message=message.strip(),
            match_id=match_id,
            job_id=job_id,
            created_at=datetime(
                2026,
                9,
                24,
                13,
                30,
                tzinfo=timezone.utc,
            ),
        )


class BugReportApiTest(
    unittest.TestCase
):
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

    def test_create_bug_report(
        self,
    ):
        repository = (
            StubBugReportRepository()
        )

        app.dependency_overrides[
            get_bug_report_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.post(
            "/bug-reports",
            json={
                "category": "analysis",
                "message": (
                    "Неверный счёт матча."
                ),
                "match_id": "match-001",
                "job_id": "job-001",
            },
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        body = response.json()

        self.assertEqual(
            body["id"],
            "report-001",
        )

        self.assertEqual(
            body["category"],
            "analysis",
        )

        self.assertEqual(
            repository.last_call[
                "owner_steam_id"
            ],
            "76561198055629469",
        )

    def test_foreign_reference_is_hidden(
        self,
    ):
        repository = (
            StubBugReportRepository(
                error=(
                    BugReportReferenceError(
                        "foreign reference"
                    )
                )
            )
        )

        app.dependency_overrides[
            get_bug_report_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.post(
            "/bug-reports",
            json={
                "category": "statistics",
                "message": (
                    "Статистика неверная."
                ),
                "match_id": "foreign-match",
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Referenced match or "
                    "analysis job not found"
                ),
            },
        )

    def test_payload_is_validated(
        self,
    ):
        repository = (
            StubBugReportRepository()
        )

        app.dependency_overrides[
            get_bug_report_repository
        ] = lambda: repository

        client = TestClient(app)

        response = client.post(
            "/bug-reports",
            json={
                "category": "banana",
                "message": "bug",
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )

        self.assertIsNone(
            repository.last_call
        )


if __name__ == "__main__":
    unittest.main()
