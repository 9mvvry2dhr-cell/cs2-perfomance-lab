import json
import unittest

from src.audit import (
    audit_actor_id,
    audit_event,
)


class AuditLogTest(unittest.TestCase):
    def test_actor_is_stable_and_does_not_expose_steam_id(self):
        steam_id = "76561198055629469"

        actor = audit_actor_id(
            steam_id
        )

        self.assertEqual(
            actor,
            audit_actor_id(
                steam_id
            ),
        )

        self.assertIsNotNone(
            actor
        )

        self.assertNotIn(
            steam_id,
            actor,
        )

    def test_event_is_structured_and_omits_raw_steam_id(self):
        steam_id = "76561198055629469"

        with self.assertLogs(
            "cs2.audit",
            level="INFO",
        ) as captured:
            audit_event(
                "demo.upload.accepted",
                steam_id=steam_id,
                job_id="job-001",
            )

        message = captured.output[0]
        marker = "AUDIT "
        payload = json.loads(
            message[
                message.index(marker)
                + len(marker):
            ]
        )

        self.assertEqual(
            payload["event"],
            "demo.upload.accepted",
        )
        self.assertEqual(
            payload["status"],
            "success",
        )
        self.assertEqual(
            payload["job_id"],
            "job-001",
        )
        self.assertNotIn(
            steam_id,
            message,
        )


if __name__ == "__main__":
    unittest.main()
