"""Regression coverage for the deployed model's content-block responses."""

import unittest

from app.model_output import output_text


class ModelOutputTests(unittest.TestCase):
    """Keep model metadata out of the rendered supervisor briefing."""

    def test_plain_text_response(self) -> None:
        self.assertEqual(output_text("  MEM needs 9 workers.\n"), "MEM needs 9 workers.")

    def test_deployed_content_blocks_include_only_visible_text(self) -> None:
        content = [
            {"type": "reasoning", "summary": [{"type": "summary_text", "text": "private metadata"}]},
            {"type": "text", "text": "MEM needs 9 workers."},
            {"type": "tool_use", "name": "unused"},
            {"type": "output_text", "text": "Supervisor approval required."},
        ]
        self.assertEqual(output_text(content), "MEM needs 9 workers.\nSupervisor approval required.")

    def test_missing_text_remains_empty(self) -> None:
        self.assertEqual(output_text(None), "")
        self.assertEqual(output_text([{"type": "reasoning", "summary": []}]), "")


if __name__ == "__main__":
    unittest.main()
