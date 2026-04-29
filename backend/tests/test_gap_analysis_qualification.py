import unittest

from app.services import nlp_service, qualification_service


class GapAnalysisQualificationTest(unittest.TestCase):
    def _build_response(
        self,
        *,
        pitch: str,
        horizon: str,
        solution: dict,
        parsed: dict | None = None,
    ):
        tags = nlp_service.normalize_tags(pitch, horizon)
        constraints = tags.sourcing_classification.constraintsForGapAnalysis if tags.sourcing_classification else None
        compressed_context = qualification_service.compress_solution_context(
            need_pitch=pitch,
            objectif=tags.objectif,
            domains_list=tags.domaine,
            impact_list=tags.impact,
            solution=solution,
            nlp_constraints=constraints,
        )
        response = qualification_service.build_gap_analysis_response(
            need_pitch=pitch,
            horizon=horizon,
            objectif=tags.objectif,
            domains_list=tags.domaine,
            impact_list=tags.impact,
            solution=solution,
            parsed=parsed or {},
            compressed_context=compressed_context,
            nlp_constraints=constraints,
            ambiguity_flags=constraints.ambiguityFlags if constraints else [],
        )
        return tags, compressed_context, response

    def test_gap_analysis_scores_match_the_five_ivi_dimensions(self) -> None:
        _tags, _compressed, response = self._build_response(
            pitch="Create a predictive maintenance model to reduce production downtime by 20% within 6 months.",
            horizon="moyen_terme",
            solution={
                "name": "Predictive Ops Copilot",
                "description": "AI platform with prediction workflows, data pipelines, API integration, and monitoring.",
                "business_impact": "Reduces downtime and improves maintenance planning through predictive insights.",
                "maturity_level": "pilot",
                "features": [
                    "Predictive maintenance model",
                    "Monitoring dashboard",
                    "API integration layer",
                    "Data quality controls",
                ],
            },
        )

        self.assertEqual(response.phase, "SG-2")
        self.assertIsNotNone(response.scores)
        self.assertEqual(
            list(response.scores.model_dump().keys()),
            ["maturite", "expertise", "duree", "donnees", "impact_business"],
        )
        for dimension in response.scores.model_dump().values():
            self.assertTrue(dimension["justification"].strip())

        self.assertIsNotNone(response.ivi_scoring)
        self.assertGreaterEqual(response.fit_score, 1)
        self.assertLessEqual(response.fit_score, 10)

    def test_risks_are_separated_from_missing_features(self) -> None:
        _tags, _compressed, response = self._build_response(
            pitch="Build a dashboard to improve production quality and reduce reporting delays.",
            horizon="court_terme",
            solution={
                "name": "Ops Quality Hub",
                "description": "Dashboard and workflow suite for production reporting.",
                "business_impact": "Improves reporting cadence for operations teams.",
                "maturity_level": "pilot",
                "features": ["Production dashboard", "Workflow approvals"],
            },
            parsed={
                "features_matching": ["Production dashboard"],
                "features_missing": ["Quality data governance is not explicitly covered."],
                "risks": ["Data mapping, quality, or integration assumptions still need validation."],
            },
        )

        self.assertTrue(response.features_missing_detail)
        self.assertTrue(response.risk_register)
        missing_names = {item.name for item in response.features_missing_detail}
        risk_titles = {item.title for item in response.risk_register}
        self.assertTrue(risk_titles.isdisjoint(missing_names))

    def test_context_filtering_prioritizes_ia_signals(self) -> None:
        tags = nlp_service.normalize_tags(
            "Creer un modele qui predit les retards de production et recommande automatiquement les actions correctives.",
            "moyen_terme",
        )
        constraints = tags.sourcing_classification.constraintsForGapAnalysis if tags.sourcing_classification else None
        compressed = qualification_service.compress_solution_context(
            need_pitch="Creer un modele qui predit les retards de production et recommande automatiquement les actions correctives.",
            objectif=tags.objectif,
            domains_list=tags.domaine,
            impact_list=tags.impact,
            solution={
                "name": "Industrial AI Suite",
                "description": "Includes predictive intelligence, workflow automation, and dashboard reporting.",
                "business_impact": "Improves production planning with intelligent scoring and anomaly detection.",
                "features": [
                    "Dashboard KPI tracking",
                    "Predictive delay model",
                    "Anomaly detection engine",
                    "Data pipeline quality checks",
                ],
            },
            nlp_constraints=constraints,
        )

        included = " ".join(compressed.audit.included_items)
        self.assertIn("Predictive delay model", included)
        self.assertIn("domain=IA", compressed.audit.filter_reason)

    def test_context_filtering_prioritizes_data_signals(self) -> None:
        tags = nlp_service.normalize_tags(
            "Creer un dashboard BI pour suivre les KPIs de production et la qualite des donnees.",
            "moyen_terme",
        )
        constraints = tags.sourcing_classification.constraintsForGapAnalysis if tags.sourcing_classification else None
        compressed = qualification_service.compress_solution_context(
            need_pitch="Creer un dashboard BI pour suivre les KPIs de production et la qualite des donnees.",
            objectif=tags.objectif,
            domains_list=tags.domaine,
            impact_list=tags.impact,
            solution={
                "name": "Data Control Tower",
                "description": "Dashboard reporting suite with BI views, storage, and predictive widgets.",
                "business_impact": "Improves KPI visibility and data-quality governance.",
                "features": [
                    "Dashboard KPI tracking",
                    "BI reporting workspace",
                    "Predictive alerting",
                    "Data quality controls",
                ],
            },
            nlp_constraints=constraints,
        )

        included = " ".join(compressed.audit.included_items)
        self.assertIn("Dashboard KPI tracking", included)
        self.assertIn("domain=Data", compressed.audit.filter_reason)

    def test_context_filtering_falls_back_when_no_relevant_subset_is_found(self) -> None:
        compressed = qualification_service.compress_solution_context(
            need_pitch="Quantum orchard synergy vision",
            objectif="market_opportunity",
            domains_list=["Autre"],
            impact_list=[],
            solution={
                "name": "Legacy Core",
                "description": "Baseline module.",
                "business_impact": "Stable service.",
                "features": ["Legacy module"],
            },
            nlp_constraints=None,
        )

        self.assertTrue(compressed.audit.fallback_to_full_context)
        self.assertIn("Legacy module", compressed.features)

    def test_calibration_caps_fit_score_and_traces_rule(self) -> None:
        _tags, _compressed, response = self._build_response(
            pitch="Reduce operating costs by 15% with better planning and predictive coordination.",
            horizon="moyen_terme",
            solution={
                "name": "Cost Planning Accelerator",
                "description": "Workflow automation, data quality controls, API integrations, and planning analytics.",
                "business_impact": "Improves planning efficiency and productivity for operations teams.",
                "maturity_level": "production",
                "features": [
                    "Planning dashboard",
                    "Automation workflows",
                    "Data quality controls",
                    "API integration layer",
                ],
            },
            parsed={
                "features_matching": [
                    "Planning dashboard",
                    "Automation workflows",
                    "API integration layer",
                ],
                "features_missing": [
                    "Predictive model capability is not clearly described.",
                    "Security controls still need to be specified.",
                    "Change-management workflow coverage remains unclear.",
                    "Advanced scenario simulation is not yet explicit.",
                ],
                "risks": ["One controlled delivery dependency remains."],
                "resources_needed": ["Assign a product owner and implementation lead."],
            },
        )

        self.assertLessEqual(response.fit_score, 5)
        calibrated_fields = {item.field for item in response.calibration_applied}
        self.assertIn("fit_score", calibrated_fields)

    def test_calibration_caps_feasibility_for_poc_and_traces_rule(self) -> None:
        _tags, _compressed, response = self._build_response(
            pitch="Automate invoice approval workflows to reduce processing time by 30% for finance operations.",
            horizon="moyen_terme",
            solution={
                "name": "Finance Flow Accelerator",
                "description": "Workflow automation, approval orchestration, API integrations, and KPI monitoring.",
                "business_impact": "Improves finance productivity and cycle-time visibility.",
                "maturity_level": "POC",
                "features": [
                    "Workflow automation",
                    "Approval orchestration",
                    "API integration layer",
                    "KPI monitoring",
                ],
            },
            parsed={
                "features_matching": [
                    "Workflow automation",
                    "Approval orchestration",
                    "API integration layer",
                ],
                "features_missing": ["Advanced analytics extension is not yet explicit."],
                "risks": ["POC maturity still requires industrialization planning."],
                "resources_needed": ["Assign a product owner and implementation lead."],
            },
        )

        self.assertLessEqual(response.feasibility.score, 3)
        calibrated_fields = {item.field for item in response.calibration_applied}
        self.assertIn("feasibility", calibrated_fields)


if __name__ == "__main__":
    unittest.main()
