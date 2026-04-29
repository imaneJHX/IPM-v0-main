import unittest

from app.services import nlp_service, qualification_service


class NlpTaggingRulesTest(unittest.TestCase):
    def test_measurable_result_without_client_forces_operational_source(self) -> None:
        tags = nlp_service.normalize_tags(
            "Reduce processing time by 2 days for the claims operations team and improve SLA performance by 20%.",
            "court_terme",
        )

        self.assertEqual(tags.origine, "probleme_operationnel")
        self.assertEqual(tags.origine_confidence, "high")
        self.assertIsNotNone(tags.sourcing_classification)
        self.assertEqual(tags.sourcing_classification.source.value, "probleme_operationnel")
        self.assertEqual(tags.sourcing_classification.source.confidence, "high")
        self.assertIn("resultat mesurable", tags.sourcing_classification.source.reason)

    def test_measurable_result_with_named_client_forces_client_source(self) -> None:
        tags = nlp_service.normalize_tags(
            "For client Carrefour, reduce invoice handling time by 2 days and save 100k on manual processing.",
            "court_terme",
        )

        self.assertEqual(tags.origine, "demande_client")
        self.assertEqual(tags.origine_confidence, "high")
        self.assertIsNotNone(tags.sourcing_classification)
        self.assertEqual(tags.sourcing_classification.source.value, "demande_client")
        self.assertEqual(tags.sourcing_classification.source.confidence, "high")

    def test_dashboard_without_inference_maps_to_data_not_ia(self) -> None:
        tags = nlp_service.normalize_tags(
            "Creer un dashboard BI pour suivre les KPIs de production, le reporting quotidien et la qualite des donnees.",
            "moyen_terme",
        )

        self.assertIn("Data", tags.domaine)
        self.assertNotIn("IA", tags.domaine)
        self.assertIsNotNone(tags.sourcing_classification)
        self.assertEqual(tags.sourcing_classification.domain.value, "Data")
        self.assertEqual(tags.sourcing_classification.domain.confidence, "high")
        self.assertIn("Data et non IA", tags.sourcing_classification.domain.reason)

    def test_prediction_or_recommendation_maps_to_ia(self) -> None:
        tags = nlp_service.normalize_tags(
            "Creer un modele qui predit les retards de production et recommande automatiquement les actions correctives.",
            "moyen_terme",
        )

        self.assertIn("IA", tags.domaine)
        self.assertIsNotNone(tags.sourcing_classification)
        self.assertEqual(tags.sourcing_classification.domain.value, "IA")
        self.assertEqual(tags.sourcing_classification.domain.confidence, "high")

    def test_short_term_horizon_biases_structured_objective_to_operational_optimization(self) -> None:
        tags = nlp_service.normalize_tags(
            "Automatiser le suivi des demandes et reduire les delais de traitement du support.",
            "court_terme",
        )

        self.assertIsNotNone(tags.sourcing_classification)
        self.assertEqual(tags.sourcing_classification.objective.value, "optimisation_operationnelle")
        self.assertTrue(tags.sourcing_classification.objective.influencedByHorizon)

    def test_long_term_horizon_biases_structured_objective_to_transformation_or_innovation(self) -> None:
        tags = nlp_service.normalize_tags(
            "Lancer une nouvelle plateforme pour transformer notre offre et soutenir la croissance future.",
            "long_terme",
        )

        self.assertIsNotNone(tags.sourcing_classification)
        self.assertIn(
            tags.sourcing_classification.objective.value,
            {"transformation_strategique", "innovation"},
        )
        self.assertTrue(tags.sourcing_classification.objective.influencedByHorizon)

    def test_output_contains_confidence_reason_and_gap_constraints(self) -> None:
        tags = nlp_service.normalize_tags(
            "Improve the service model for future growth.",
            "long_terme",
        )

        self.assertIsNotNone(tags.sourcing_classification)
        self.assertTrue(tags.sourcing_classification.source.reason)
        self.assertTrue(tags.sourcing_classification.domain.reason)
        self.assertTrue(tags.sourcing_classification.objective.reason)
        self.assertIsNotNone(tags.gap_analysis_constraints)
        self.assertIsNotNone(tags.gap_analysis_constraints.constraintsForGapAnalysis)
        self.assertEqual(tags.gap_analysis_constraints.phase, "SG-1")
        self.assertEqual(
            tags.gap_analysis_constraints.constraintsForGapAnalysis.objective,
            tags.sourcing_classification.constraintsForGapAnalysis.objective,
        )

    def test_gap_analysis_accepts_nlp_constraints_without_regression(self) -> None:
        tags = nlp_service.normalize_tags(
            "Creer un dashboard BI pour suivre les KPIs de production et reduire les erreurs de 20%.",
            "court_terme",
        )
        solution = {
            "name": "Ops Control Dashboard",
            "description": "Pilot analytics workspace with workflow monitoring, dashboarding, and API integrations.",
            "business_impact": "Improves production reporting, control, and operational visibility.",
            "maturity_level": "pilot",
            "features": [
                "Dashboard KPI tracking",
                "Reporting automation",
                "API integrations",
            ],
        }
        compressed_context = qualification_service.compress_solution_context(
            need_pitch="Creer un dashboard BI pour suivre les KPIs de production et reduire les erreurs de 20%.",
            objectif=tags.objectif,
            domains_list=tags.domaine,
            impact_list=tags.impact,
            solution=solution,
        )

        response = qualification_service.build_gap_analysis_response(
            need_pitch="Creer un dashboard BI pour suivre les KPIs de production et reduire les erreurs de 20%.",
            horizon="court_terme",
            objectif=tags.objectif,
            domains_list=tags.domaine,
            impact_list=tags.impact,
            solution=solution,
            parsed={},
            compressed_context=compressed_context,
            nlp_constraints=tags.sourcing_classification.constraintsForGapAnalysis if tags.sourcing_classification else None,
            ambiguity_flags=tags.sourcing_classification.constraintsForGapAnalysis.ambiguityFlags if tags.sourcing_classification else [],
        )

        self.assertGreaterEqual(response.fit_score, 1)
        self.assertLessEqual(response.fit_score, 10)
        self.assertIsNotNone(response.audit.nlp_constraints)
        self.assertEqual(response.audit.nlp_constraints.domain, "Data")
        applied_rule_codes = {rule.code for rule in response.audit.applied_rules}
        self.assertIn("nlp_constraints_received", applied_rule_codes)


if __name__ == "__main__":
    unittest.main()
