import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import (
    _ai_coach_enabled,
    app,
)


class PublicSurfaceSecurityTest(
    unittest.TestCase
):
    def test_api_docs_are_disabled(self):
        client = TestClient(app)

        for path in (
            "/docs",
            "/redoc",
            "/openapi.json",
        ):
            with self.subTest(
                path=path
            ):
                response = client.get(
                    path
                )

                self.assertEqual(
                    response.status_code,
                    404,
                )

    def test_ai_kill_switch_can_disable_generation(self):
        with patch.dict(
            os.environ,
            {
                "AI_COACH_ENABLED":
                    "false",
            },
            clear=False,
        ):
            self.assertFalse(
                _ai_coach_enabled()
            )

    def test_ai_kill_switch_defaults_to_enabled(self):
        with patch.dict(
            os.environ,
            {},
            clear=False,
        ):
            old_value = os.environ.pop(
                "AI_COACH_ENABLED",
                None,
            )

            try:
                self.assertTrue(
                    _ai_coach_enabled()
                )

            finally:
                if old_value is not None:
                    os.environ[
                        "AI_COACH_ENABLED"
                    ] = old_value


if __name__ == "__main__":
    unittest.main()
