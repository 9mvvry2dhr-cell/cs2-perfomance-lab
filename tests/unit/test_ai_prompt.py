import json
import unittest

from src.ai.payload import build_match_ai_payload
from src.ai.prompt import (
    AI_PROMPT_VERSION,
    MATCH_AI_INSTRUCTIONS,
    build_match_ai_prompt,
)
from tests.unit.test_analysis_repository import make_analysis


class MatchAIPromptTest(unittest.TestCase):

    def _prompt(self):
        analysis = make_analysis()

        payload = build_match_ai_payload(
            analysis,
            steam_id="76561198055629469",
        )

        return build_match_ai_prompt(
            payload
        )


    def test_prompt_version_is_v1(self):
        self.assertEqual(
            AI_PROMPT_VERSION,
            "v1",
        )


    def test_prompt_requires_verified_findings_for_strengths_and_weaknesses(self):
        prompt = self._prompt()

        self.assertIn(
            "verified_findings as the only allowed strength/weakness conclusions",
            prompt.instructions,
        )

        self.assertIn(
            "Every strength or weakness you mention must be supported by a verified finding",
            prompt.instructions,
        )


    def test_prompt_forbids_hidden_cause_invention(self):
        prompt = self._prompt()

        for phrase in (
            "bad positioning",
            "aim",
            "timing",
            "communication",
            "decision-making",
            "tilt",
            "fatigue",
            "game sense",
        ):
            with self.subTest(
                phrase=phrase
            ):
                self.assertIn(
                    phrase,
                    prompt.instructions,
                )


    def test_prompt_requests_json_contract(self):
        prompt = self._prompt()

        for key in (
            '"summary"',
            '"strengths"',
            '"weaknesses"',
            '"focus"',
            '"caveat"',
            '"evidence_codes"',
        ):
            with self.subTest(
                key=key
            ):
                self.assertIn(
                    key,
                    prompt.instructions,
                )


    def test_prompt_forbids_team_result_inference_from_ct_t_score(self):
        prompt = self._prompt()

        self.assertIn(
            "do NOT tell you whether the player's team won or lost",
            prompt.instructions,
        )

        self.assertIn(
            'match.player_result explicitly says "win" or "loss"',
            prompt.instructions,
        )

        self.assertIn(
            'match.player_result is "unknown"',
            prompt.instructions,
        )


    def test_input_contains_exact_verified_payload(self):
        analysis = make_analysis()

        payload = build_match_ai_payload(
            analysis,
            steam_id="76561198055629469",
        )

        prompt = build_match_ai_prompt(
            payload
        )

        prefix = (
            "Explain this verified CS2 Performance Lab payload.\n\n"
        )

        self.assertTrue(
            prompt.input_text.startswith(
                prefix
            )
        )

        encoded = prompt.input_text[
            len(prefix):
        ]

        self.assertEqual(
            json.loads(encoded),
            payload,
        )


    def test_instructions_do_not_contain_user_identifiers(self):
        prompt = self._prompt()

        self.assertNotIn(
            "76561198055629469",
            prompt.instructions,
        )

        self.assertNotIn(
            "match730_",
            prompt.instructions,
        )


if __name__ == "__main__":
    unittest.main()
