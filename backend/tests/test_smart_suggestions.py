import asyncio
import unittest
from unittest.mock import patch

from app.services import nlp_service


class SmartSuggestionsTest(unittest.TestCase):
    def test_mobile_ux_suggestions_are_generated_in_english(self) -> None:
        with patch("app.services.nlp_service._llm_is_configured", return_value=False):
            tags, suggestions = asyncio.run(
                nlp_service.analyze_pitch(
                    "improve mobile ux",
                    "moyen_terme",
                    objective="cost_reduction",
                    domains=["Data"],
                    impacts=["Cost"],
                    tags=["cost_reduction", "Data", "Cost", "probleme_operationnel"],
                    phase="SG-1",
                    status="Draft",
                )
            )

        self.assertGreaterEqual(len(suggestions), 3)
        combined = " ".join(
            f"{item.title} {item.explanation} {item.improved_pitch or ''} {item.next_action}"
            for item in suggestions
        ).lower()
        self.assertNotIn(" veuillez ", f" {combined} ")
        self.assertNotIn(" ajoutez ", f" {combined} ")
        self.assertNotIn(" dans les ", f" {combined} ")

    def test_mobile_ux_suggestions_reference_measurable_ux_kpis(self) -> None:
        with patch("app.services.nlp_service._llm_is_configured", return_value=False):
            _tags, suggestions = asyncio.run(
                nlp_service.analyze_pitch(
                    "improve mobile ux",
                    "moyen_terme",
                    objective="cost_reduction",
                    domains=["Data"],
                    impacts=["Cost"],
                    tags=["cost_reduction", "Data", "Cost", "probleme_operationnel"],
                    phase="SG-1",
                    status="Draft",
                )
            )

        combined = " ".join(
            f"{item.explanation} {item.improved_pitch or ''} {item.next_action}"
            for item in suggestions
        ).lower()
        self.assertTrue(
            any(keyword in combined for keyword in ("conversion", "task completion", "abandonment", "support-ticket", "support requests"))
        )

    def test_mobile_ux_cost_context_suggests_customer_experience_as_additional_impact(self) -> None:
        with patch("app.services.nlp_service._llm_is_configured", return_value=False):
            _tags, suggestions = asyncio.run(
                nlp_service.analyze_pitch(
                    "improve mobile ux",
                    "court_terme",
                    objective="cost_reduction",
                    domains=["Data"],
                    impacts=["Cost"],
                    tags=["cost_reduction", "Data", "Cost", "probleme_operationnel"],
                    phase="SG-1",
                    status="Draft",
                )
            )

        impact_review = next((item for item in suggestions if item.action_type == "apply_tag"), None)
        self.assertIsNotNone(impact_review)
        self.assertIn("CustomerExperience", impact_review.suggested_tags)
        self.assertEqual(impact_review.category, "Customer Experience")


if __name__ == "__main__":
    unittest.main()
