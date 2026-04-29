import asyncio
import unittest
from unittest.mock import patch

from app.core import llm_client
from app.services import recommendation_service


class SolutionRecommendationsTest(unittest.TestCase):
    def _build_solution(self, *, fit_score: int = 6) -> dict:
        return {
            "id": "SOL-001",
            "name": "Predictive Service Accelerator",
            "description": "Enterprise solution for workflow orchestration, intelligent triage, and observability.",
            "source": "DXC catalog",
            "features": [
                "Workflow orchestration",
                "Monitoring dashboard",
                "API integration framework",
            ],
            "business_impact": "Improves efficiency and customer responsiveness.",
            "maturity_level": "pilot",
            "gap_analysis": {
                "fit_score": fit_score,
                "prerequisite_mode": fit_score <= 4,
                "features_missing": [
                    "Predictive scoring engine",
                    "Customer notification workflow",
                ],
                "resources_needed": [
                    "Data quality owner",
                    "Integration architect",
                ],
                "risks": [
                    "Data access and privacy controls still need validation.",
                ],
                "audit": {
                    "nlp_constraints": {
                        "domain": "IA",
                        "objective": "automatisation",
                        "impact": ["Cost", "CustomerExperience"],
                        "horizon": "moyen_terme",
                    }
                },
            },
        }

    def _generate(self, *, fit_score: int = 6):
        with patch("app.services.recommendation_service._optional_llm_enrichment", return_value={}):
            return asyncio.run(
                recommendation_service.generate_solution_recommendations(
                    need_pitch="Reduce customer handling time and operating cost with intelligent triage.",
                    horizon="moyen_terme",
                    objectif="cost_reduction",
                    impact_list=["Cost", "CustomerExperience"],
                    domains_list=["IA", "Process"],
                    selected_solution=self._build_solution(fit_score=fit_score),
                )
            )

    def test_each_missing_feature_generates_a_named_technical_recommendation(self) -> None:
        response = self._generate(fit_score=6)

        covered = {
            feature
            for recommendation in response.technical_recommendations
            for feature in recommendation.related_feature_missing
        }
        for feature in self._build_solution()["gap_analysis"]["features_missing"]:
            self.assertIn(feature, covered)

    def test_technical_recommendations_reference_missing_features_nominatively(self) -> None:
        response = self._generate(fit_score=6)
        known_features = set(self._build_solution()["gap_analysis"]["features_missing"])

        for recommendation in response.technical_recommendations:
            self.assertTrue(recommendation.related_feature_missing)
            self.assertTrue(set(recommendation.related_feature_missing).issubset(known_features))

    def test_each_resource_needed_generates_an_organizational_recommendation_with_owner(self) -> None:
        response = self._generate(fit_score=6)
        covered_resources = {item.related_resource_needed for item in response.organizational_recommendations}

        for resource in self._build_solution()["gap_analysis"]["resources_needed"]:
            self.assertIn(resource, covered_resources)
        for recommendation in response.organizational_recommendations:
            self.assertTrue(recommendation.responsible_role)

    def test_cost_and_customer_experience_impacts_force_required_kpi_units(self) -> None:
        response = self._generate(fit_score=6)
        units = {kpi.unit for kpi in response.kpis}

        self.assertTrue(any(unit in {"€", "%"} for unit in units))
        self.assertTrue(any(unit in {"minutes", "hours", "days"} for unit in units))

    def test_dxc_prompt_mentions_required_ecosystem_terms(self) -> None:
        prompt = llm_client.FALLBACK_PROMPTS["solution-recommendations-v2"]["system"]

        self.assertIn("Microsoft", prompt)
        self.assertIn("SAP", prompt)
        self.assertIn("ServiceNow", prompt)
        self.assertIn("AWS", prompt)
        self.assertIn("ITIL", prompt)

    def test_fit_score_below_or_equal_four_switches_to_prerequisite_mode(self) -> None:
        response = self._generate(fit_score=4)

        self.assertEqual(response.delivery_mode, "PREREQUISITE")
        self.assertTrue(response.prerequisite_reason.strip())
        self.assertTrue(response.prerequisite_actions)

    def test_fit_score_above_four_keeps_delivery_mode(self) -> None:
        response = self._generate(fit_score=7)

        self.assertEqual(response.delivery_mode, "DELIVERY")
        self.assertFalse(response.prerequisite_actions)

    def test_coverage_validation_returns_true_when_all_mappings_are_covered(self) -> None:
        response = self._generate(fit_score=6)

        self.assertTrue(response.coverage_validation.features_missing_covered)
        self.assertTrue(response.coverage_validation.resources_needed_covered)
        self.assertTrue(response.coverage_validation.kpi_rules_satisfied)
        self.assertEqual(response.coverage_validation.missing_coverage, [])

    def test_coverage_validation_signals_uncovered_items_when_generation_is_incomplete(self) -> None:
        with (
            patch("app.services.recommendation_service._optional_llm_enrichment", return_value={}),
            patch("app.services.recommendation_service._apply_llm_enrichment_to_technical", return_value=[]),
            patch(
                "app.services.recommendation_service._ensure_feature_coverage",
                return_value=([], [], []),
            ),
        ):
            response = asyncio.run(
                recommendation_service.generate_solution_recommendations(
                    need_pitch="Reduce customer handling time and operating cost with intelligent triage.",
                    horizon="moyen_terme",
                    objectif="cost_reduction",
                    impact_list=["Cost", "CustomerExperience"],
                    domains_list=["IA", "Process"],
                    selected_solution=self._build_solution(fit_score=6),
                )
            )

        self.assertFalse(response.coverage_validation.features_missing_covered)
        self.assertIn("Predictive scoring engine", response.coverage_validation.missing_coverage)


if __name__ == "__main__":
    unittest.main()
