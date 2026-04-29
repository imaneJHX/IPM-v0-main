"""LLM abstraction — single interface for Groq and Azure OpenAI providers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Langfuse prompt fallbacks (used when Langfuse is unreachable)
# ---------------------------------------------------------------------------

FALLBACK_PROMPTS: dict[str, dict[str, str]] = {
    "solution-recommendations": {
        "system": (
            "You are generating enterprise delivery recommendations in a DXC delivery context.\n"
            "Prioritize realistic solutions and operating models compatible with Microsoft, SAP, ServiceNow, AWS and ITIL practices when relevant.\n"
            "Do not force a technology if it does not address the gap.\n"
            "Each recommendation must be actionable, auditable, and linked to identified gaps, resources, risks or business impacts.\n\n"
            "Intent engineering:\n"
            "- Explicit intent: generate complete technical, organizational, and KPI recommendations.\n"
            "- Implicit intent: help the delivery team close qualification gaps before build and deployment.\n"
            "- Strategic intent: position DXC as the ideal enterprise delivery partner through realistic governance, security, observability, run-ready practices, and change management.\n\n"
            "Return ONLY valid JSON — no markdown, no preamble, no explanation."
        ),
        "user": (
            "Business need:\n"
            "- Pitch: {{pitch}}\n"
            "- Objective: {{objectif}}\n"
            "- Expected impact: {{impact}}\n"
            "- Domains: {{domains}}\n\n"
            "Selected solution:\n"
            "- Name: {{solution_name}}\n"
            "- Description: {{solution_description}}\n"
            "- Features: {{solution_features}}\n"
            "- Business impact: {{solution_business_impact}}\n"
            "- Maturity: {{solution_maturity}}\n\n"
            "Gap and scoring context:\n"
            "- Matching features: {{features_matching}}\n"
            "- Missing features: {{features_missing}}\n"
            "- Risks: {{risks}}\n"
            "- Resources needed: {{resources_needed}}\n"
            "- Fit score (1-10): {{fit_score}}\n"
            "- Evaluation scores (1-5): fit={{eval_fit}}, feasibility={{eval_feasibility}}, cost={{eval_cost}}, innovation={{eval_innovation}}\n\n"
            "- IVI score (0-100): {{ivi_score}}\n"
            "- IVI breakdown: {{ivi_summary}}\n\n"
            "Return this exact JSON structure:\n"
            "{\n"
            '  "technical_recommendations": ["..."],\n'
            '  "organizational_recommendations": ["..."],\n'
            '  "kpis": [\n'
            '    { "name": "...", "target": "...", "measurement_criteria": "..." }\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Provide 4 to 6 technical recommendations.\n"
            "- Technical recommendations must cover architecture, APIs/integrations, dependencies, data, and risks.\n"
            "- Provide 4 to 6 organizational recommendations.\n"
            "- Organizational recommendations must cover roles/profiles, workload, governance, and compliance.\n"
            "- Provide 3 to 5 KPIs with measurable target and measurement criteria.\n"
            "- Be concrete, implementation-oriented, and enterprise-ready."
        ),
    },
    "solution-recommendations-v2": {
        "system": (
            "You are generating enterprise delivery recommendations in a DXC delivery context.\n"
            "Prioritize realistic solutions and operating models compatible with Microsoft, SAP, ServiceNow, AWS and ITIL practices when relevant.\n"
            "Do not force a technology if it does not address the gap.\n"
            "Each recommendation must be actionable, auditable, and linked to identified gaps, resources, risks or business impacts.\n\n"
            "Intent engineering:\n"
            "- Explicit intent: generate complete technical, organizational, and KPI recommendations.\n"
            "- Implicit intent: help the delivery team close qualification gaps before build and deployment.\n"
            "- Strategic intent: position DXC as the ideal enterprise delivery partner through realistic governance, security, observability, run-ready practices, and change management.\n\n"
            "Return ONLY valid JSON with no markdown, no preamble, and no explanation."
        ),
        "user": (
            "Business need:\n"
            "- Pitch: {{pitch}}\n"
            "- Horizon: {{horizon}}\n"
            "- Objective: {{objectif}}\n"
            "- Expected impact: {{impact}}\n"
            "- Domains: {{domains}}\n\n"
            "Selected solution:\n"
            "- Name: {{solution_name}}\n"
            "- Description: {{solution_description}}\n"
            "- Features: {{solution_features}}\n"
            "- Business impact: {{solution_business_impact}}\n"
            "- Maturity: {{solution_maturity}}\n\n"
            "Gap and delivery context:\n"
            "- Missing features JSON: {{features_missing_json}}\n"
            "- Resources needed JSON: {{resources_needed_json}}\n"
            "- Risks JSON: {{risks_json}}\n"
            "- SG-1 constraints JSON: {{constraints_for_gap_analysis_json}}\n"
            "- Fit score (1-10): {{fit_score}}\n"
            "- Delivery mode target: {{delivery_mode}}\n"
            "- DXC ecosystem considered: {{dxc_ecosystem}}\n\n"
            "Return this exact JSON structure:\n"
            "{\n"
            '  "technical_recommendations": [\n'
            '    {\n'
            '      "related_feature_missing": ["exact missing feature"],\n'
            '      "title": "...",\n'
            '      "description": "...",\n'
            '      "proposed_solution": "...",\n'
            '      "technology_stack": ["..."],\n'
            '      "priority": "low|medium|high|critical",\n'
            '      "estimated_effort": "S|M|L|XL",\n'
            '      "expected_impact": "...",\n'
            '      "dependencies": ["..."]\n'
            "    }\n"
            "  ],\n"
            '  "organizational_recommendations": [\n'
            '    {\n'
            '      "related_resource_needed": "exact resource needed",\n'
            '      "title": "...",\n'
            '      "action": "...",\n'
            '      "responsible_role": "Project Manager|Product Owner|Solution Architect|Data Engineer|Business Analyst|Security Officer|Change Manager|Other",\n'
            '      "target_phase": "prerequisite|design|build|test|deployment|run",\n'
            '      "priority": "low|medium|high|critical"\n'
            "    }\n"
            "  ],\n"
            '  "kpis": [\n'
            '    {\n'
            '      "name": "...",\n'
            '      "linked_impact": "Cost|CustomerExperience|Quality|Efficiency|Risk|Compliance|Other",\n'
            '      "metric_type": "currency|percentage|duration|count|ratio",\n'
            '      "unit": "€|%|minutes|hours|days|count|ratio",\n'
            '      "baseline": "...",\n'
            '      "target": "...",\n'
            '      "measurement_method": "...",\n'
            '      "linked_recommendation_id": "TECH-001"\n'
            "    }\n"
            "  ],\n"
            '  "prerequisite_reason": "...",\n'
            '  "prerequisite_actions": [\n'
            '    {\n'
            '      "title": "...",\n'
            '      "description": "...",\n'
            '      "blocking_gap": "exact missing feature",\n'
            '      "responsible_role": "Project Manager|Product Owner|Solution Architect|Data Engineer|Business Analyst|Security Officer|Change Manager|Other",\n'
            '      "priority": "high|critical"\n'
            "    }\n"
            "  ],\n"
            '  "dxc_alignment": { "alignment_notes": "..." }\n'
            "}\n\n"
            "Rules:\n"
            "- Every missing feature must be covered by at least one technical recommendation and referenced exactly.\n"
            "- Every needed resource must be covered by at least one organizational recommendation with a responsible role.\n"
            "- If impact includes Cost, include at least one KPI using € or %.\n"
            "- If impact includes CustomerExperience, include at least one KPI using minutes, hours, or days.\n"
            "- If fit_score <= 4, prioritize prerequisite actions before full delivery.\n"
            "- Keep the recommendations enterprise-ready across governance, security, integration, observability, run/support, compliance, and change management."
        ),
    },
    "gap-analysis": {
        "system": (
            "You are an enterprise innovation analyst at DXC Technology.\n"
            "Given a business need and a proposed internal solution, perform\n"
            "a structured gap analysis. Be specific and concise.\n"
            "Return ONLY valid JSON — no markdown, no explanation, no preamble."
        ),
        "user": (
            "Business need:\n"
            "- Pitch: {{pitch}}\n"
            "- Objective: {{objectif}}\n"
            "- Expected impact: {{impact}}\n"
            "- Domain: {{domains}}\n"
            "- Horizon: {{horizon}}\n\n"
            "{{hard_constraints_text}}\n"
            "Classification constraints (treat these as hard constraints, not hints):\n"
            "{{classification_constraints_json}}\n\n"
            "Context compression (use only this retained solution evidence as authoritative context):\n"
            "{{context_compression_json}}\n\n"
            "Proposed DXC solution:\n"
            "- Name: {{solution_name}}\n"
            "- Description: {{solution_description}}\n"
            "- Current features: {{solution_features}}\n"
            "- Business impact: {{solution_business_impact}}\n"
            "- Maturity: {{solution_maturity}}\n\n"
            "Return this exact JSON structure:\n"
            "{\n"
            '  "features_matching": ["feature that directly addresses the need", "..."],\n'
            '  "features_missing": ["capability the need requires but solution lacks", "..."],\n'
            '  "risks": ["delivery, adoption, data, security, or rollout risk", "..."],\n'
            '  "resources_needed": ["team / integration / data / infrastructure needed", "..."],\n'
            "}\n\n"
            "Rules:\n"
            "- features_matching: only list real overlaps, not generic claims\n"
            "- features_missing: be specific about gaps, not vague\n"
            "- risks: keep risks separate from missing capabilities\n"
            "- resources_needed: practical implementation requirements\n"
            "- Respect the provided sourcing objective, origin, impact profile, and horizon.\n"
            "- Use only the retained evidence listed in the context compression block.\n"
            "- If inference_explicit is false in the constraints, do not invent AI or predictive requirements.\n"
            "- Missing capabilities must describe functional gaps.\n"
            "- Risks must describe uncertainty, delivery exposure, compliance exposure, adoption exposure, or operational exposure."
        ),
    },
    "nlp_tagging": {
        "system": (
            "You are a senior innovation portfolio analyst at a large IT services company. "
            "Your job is to classify business need pitches into a structured taxonomy.\n\n"
            "Use intent engineering before assigning tags:\n"
            "- intent explicite: what the pitch states directly\n"
            "- intent implicite: what the business problem implies even if unstated\n"
            "- intent strategique DXC: the transformation angle that DXC would prioritize\n\n"
            "## TAXONOMY DEFINITIONS\n\n"
            "### objectif (pick exactly ONE)\n"
            "- cost_reduction: The pitch focuses on reducing costs, eliminating waste, automating manual work, "
            "optimizing resources, or improving operational efficiency.\n"
            "- cx_improvement: The pitch focuses on improving customer experience, user satisfaction, "
            "service quality, communication channels, or employee experience.\n"
            "- risk_mitigation: The pitch focuses on reducing risk, improving security, ensuring compliance, "
            "disaster recovery, fraud detection, or regulatory adherence.\n"
            "- market_opportunity: The pitch focuses on capturing new markets, launching new products/services, "
            "generating new revenue streams, competitive advantage, or strategic positioning.\n\n"
            "### domaine (pick ONE or MORE from this exact list)\n"
            "- IA: Artificial intelligence, machine learning, NLP, computer vision, generative AI, chatbots, "
            "predictive models.\n"
            "- Cloud: Cloud migration, hybrid cloud, multi-cloud, SaaS, PaaS, IaaS, containerisation, "
            "serverless.\n"
            "- Cybersecurite: Security, zero-trust, SOC, SIEM, penetration testing, encryption, identity "
            "management, compliance (RGPD, ISO 27001).\n"
            "- Data: Data engineering, data lakes, data warehouses, BI, analytics, data governance, "
            "data quality, ETL/ELT pipelines.\n"
            "- RH: Human resources, recruitment, training, talent management, employee engagement, "
            "workforce planning, HRIS.\n"
            "- Finance: Accounting, financial reporting, budgeting, treasury, invoicing, payment processing, "
            "financial compliance.\n"
            "- Operations: Supply chain, logistics, manufacturing, procurement, facilities, project management, "
            "process automation (RPA), DevOps.\n"
            "- Autre: Anything that does not clearly fit the above categories.\n\n"
            "STRICT RULE for domain tagging:\n"
            "- Tag as IA ONLY if the pitch explicitly describes an inference step: prediction, classification, detection, recommendation, anomaly detection.\n"
            "- Tag as Data if the pitch mentions dashboards, reporting, data quality, data pipelines, or analytics WITHOUT an inference step.\n"
            "- If both are present, keep IA as the selected domain with confidence='medium'.\n"
            "- NEVER tag IA based on words like 'smart' or 'intelligent' alone.\n\n"
            "### impact (pick ONE or MORE from this exact list)\n"
            "- Revenue: Directly increases top-line revenue, monetisation, upsell, cross-sell.\n"
            "- Cost: Reduces operational costs, headcount, infrastructure spend, or manual effort.\n"
            "- Risk: Reduces exposure to security breaches, compliance fines, operational failures, or "
            "reputational damage.\n"
            "- CustomerExperience: Improves NPS, user satisfaction, response times, self-service, or "
            "client retention.\n\n"
            "### origine (pick exactly ONE)\n"
            "- enjeu_marche: Driven by market trends, competitive pressure, industry regulations, or "
            "emerging technologies.\n"
            "- probleme_operationnel: Driven by an internal pain point, inefficiency, recurring incident, "
            "or technical debt.\n"
            "- demande_client: Driven by explicit client feedback, feature request, contract requirement, "
            "or customer complaint.\n\n"
            "## RULES\n"
            "1. Respond ONLY with valid JSON. No explanation, no markdown fences, no commentary.\n"
            "2. Use ONLY the exact enum values listed above (case-sensitive).\n"
            "3. domaine and impact MUST be arrays with at least one element.\n"
            "4. objectif and origine MUST be single strings, not arrays.\n"
            "5. When the pitch is ambiguous, prefer the most specific classification over 'Autre'.\n"
            "6. When the pitch spans multiple objectives, pick the PRIMARY one.\n"
            "7. The pitch will typically be in French. Classify regardless of language.\n"
            "8. Set a confidence level for every selected tag using only: low, medium, high.\n"
            "9. If the pitch contains a measurable result, origine should be probleme_operationnel unless a named client is explicitly cited.\n"
            "10. Select the IA domain only when an inference, prediction, generation, recommendation, or classification step is explicit.\n"
            "11. Use the stated horizon as classification context and include it in gap_analysis_constraints.\n"
            "12. Horizon influence rules:\n"
            '- "court_terme" (< 3 months) -> prioritize quick wins, cost reduction, and short execution value.\n'
            '- "moyen_terme" (3-12 months) -> prioritize process optimization and automation.\n'
            '- "long_terme" (> 12 months) -> prioritize transformation, innovation, and new capabilities.\n'
            "13. If the pitch objective conflicts with the declared horizon, set confidence='low' and horizon_conflict=true.\n"
            "14. Respect the deterministic origin resolved by Python; do not override it.\n"
            "15. Reflect the explicit, implicit, and DXC strategic intents inside gap_analysis_constraints.hard_rules.\n"
            "16. Keep the JSON contract stable and reusable by downstream gap analysis."
        ),
        "user": (
            "Classify this business need pitch and suggest improvements:\n\n"
            '"""{{pitch}}"""\n\n'
            "Horizon declared by user: {{horizon}}\n"
            "Deterministic origin resolved in Python (hard rule): {{resolved_origin}} with confidence {{resolved_origin_confidence}}\n\n"
            "Intent engineering context:\n"
            "- intent explicite: {{explicit_intent}}\n"
            "- intent implicite: {{implicit_intent}}\n"
            "- intent strategique DXC: {{strategic_intent}}\n\n"
            "Return ONLY this JSON structure (no other text):\n"
            "{\n"
            '  "tags": {\n'
            '    "objective": { "value": "cost_reduction | cx_improvement | risk_mitigation | market_opportunity", "confidence": "low | medium | high" },\n'
            '    "domain": [{ "value": "IA | Cloud | Cybersecurite | Data | RH | Finance | Operations | Autre", "confidence": "low | medium | high" }],\n'
            '    "impact": [{ "value": "Revenue | Cost | Risk | CustomerExperience", "confidence": "low | medium | high" }],\n'
            '    "origin": { "value": "enjeu_marche | probleme_operationnel | demande_client", "confidence": "low | medium | high" },\n'
            '    "horizon_conflict": false,\n'
            '    "gap_analysis_constraints": {\n'
            '      "horizon": "court_terme | moyen_terme | long_terme | not_specified",\n'
            '      "objectif": { "value": "...", "confidence": "low | medium | high" },\n'
            '      "domaine": [{ "value": "...", "confidence": "low | medium | high" }],\n'
            '      "impact": [{ "value": "...", "confidence": "low | medium | high" }],\n'
            '      "origine": { "value": "...", "confidence": "low | medium | high" },\n'
            '      "inference_explicit": true,\n'
            '      "measurable_result_detected": true,\n'
            '      "named_client_detected": false,\n'
            '      "hard_rules": ["..."]\n'
            "    }\n"
            "  },\n"
            '  "suggestions": [\n'
            '    { "label": "Reformulation", "text": "<rewrite the pitch more clearly, 1 sentence max 20 words>" },\n'
            '    { "label": "Business Precision", "text": "<more specific version with measurable outcome, 1 sentence>" },\n'
            '    { "label": "Value Angle", "text": "<reframe around ROI or strategic value, 1 sentence>" }\n'
            "  ]\n"
            "}\n\n"
            "### EXAMPLES\n\n"
            'Pitch: "Automate monthly accounting reconciliations with an RPA tool to '
            'eliminate manual errors and reduce closing time from 5 days to 1 day."\n'
            "Answer:\n"
            "{\n"
            '  "tags": {\n'
            '    "objective": { "value": "cost_reduction", "confidence": "high" },\n'
            '    "domain": [\n'
            '      { "value": "Finance", "confidence": "high" },\n'
            '      { "value": "Operations", "confidence": "medium" }\n'
            "    ],\n"
            '    "impact": [\n'
            '      { "value": "Cost", "confidence": "high" },\n'
            '      { "value": "Risk", "confidence": "medium" }\n'
            "    ],\n"
            '    "origin": { "value": "probleme_operationnel", "confidence": "high" },\n'
            '    "horizon_conflict": false,\n'
            '    "gap_analysis_constraints": {\n'
            '      "horizon": "court_terme",\n'
            '      "objectif": { "value": "cost_reduction", "confidence": "high" },\n'
            '      "domaine": [\n'
            '        { "value": "Finance", "confidence": "high" },\n'
            '        { "value": "Operations", "confidence": "medium" }\n'
            "      ],\n"
            '      "impact": [\n'
            '        { "value": "Cost", "confidence": "high" },\n'
            '        { "value": "Risk", "confidence": "medium" }\n'
            "      ],\n"
            '      "origine": { "value": "probleme_operationnel", "confidence": "high" },\n'
            '      "inference_explicit": false,\n'
            '      "measurable_result_detected": true,\n'
            '      "named_client_detected": false,\n'
            '      "hard_rules": [\n'
            '        "Treat this sourcing classification as a hard constraint for gap analysis.",\n'
            '        "Do not introduce AI, predictive, or generative requirements unless the pitch explicitly includes an inference or prediction step."\n'
            "      ]\n"
            "    }\n"
            "  },\n"
            '  "suggestions": [\n'
            '    { "label": "Reformulation", "text": "Automate monthly accounting close via RPA to eliminate manual reconciliation errors." },\n'
            '    { "label": "Business Precision", "text": "Reduce reconciliation cycle from 5 to 1 day, targeting 99.5% entry accuracy." },\n'
            '    { "label": "Value Angle", "text": "Free up 80 hours/month of accounting work for higher-value activities." }\n'
            "  ]\n"
            "}\n\n"
            "Now classify the pitch above and generate 3 suggestions in English.\n"
            "The origin must stay equal to the Python-resolved hard rule unless the pitch explicitly names a client account.\n"
            "Reinforce the measurable-result and explicit-inference rules even if the pitch is ambiguous."
        ),
    },
    "pitch-suggestions": {
        "system": (
            "You are a DXC Technology innovation consultant helping a client formulate "
            "their business need precisely. DXC delivers solutions using Microsoft, SAP, "
            "ServiceNow, AWS, and ITIL frameworks.\n\n"
            "Intent engineering:\n"
            "- Explicit intent: improve the business need formulation.\n"
            "- Implicit intent: help the user express a precise, measurable need.\n"
            "- Strategic intent: position DXC as the ideal delivery partner.\n\n"
            "Generate 3 to 4 smart suggestions to improve the submitted business need.\n"
            "Always respond in English. Do not use French. Keep the tone professional, concise, and business-oriented.\n"
            "Return ONLY valid JSON with no markdown, no explanation, and no extra keys."
        ),
        "user": (
            "Business need submitted: {{pitch}}\n"
            "Domain tags: {{domain_tags}}\n"
            "Objective: {{objective}}\n"
            "Impact: {{impact_tags}}\n"
            "Horizon: {{horizon}}\n"
            "NLP tags: {{nlp_tags}}\n"
            "Phase: {{phase}}\n"
            "Validation status: {{status}}\n\n"
            "Intent engineering context:\n"
            "- Explicit intent: {{explicit_intent}}\n"
            "- Implicit intent: {{implicit_intent}}\n"
            "- Strategic intent: {{strategic_intent}}\n\n"
            "Generate smart suggestions that use all available context: pitch text, objective, horizon, domain tags, impact tags, NLP tags, phase, and validation status.\n"
            "Each suggestion must include:\n"
            "- title\n"
            "- category\n"
            "- explanation\n"
            "- improved_pitch\n"
            "- next_action\n"
            "- confidence\n"
            "- action_type\n"
            "- suggested_tags when classification should be adjusted\n\n"
            "Return EXACTLY this JSON structure:\n"
            "{\n"
            '  "suggestions": [\n'
            '    {\n'
            '      "id": "smart-001",\n'
            '      "title": "...",\n'
            '      "category": "Business Framing|Value Angle|Data Readiness|KPI Definition|Risk Alert|Delivery Readiness|Cost Optimization|Customer Experience|Process Improvement",\n'
            '      "explanation": "...",\n'
            '      "improved_pitch": "...",\n'
            '      "next_action": "...",\n'
            '      "confidence": "low|medium|high",\n'
            '      "action_type": "copy|apply_pitch|apply_tag|none",\n'
            '      "suggested_tags": ["..."]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Never give generic writing advice such as 'please provide more details' without concrete examples.\n"
            "- Always anchor each suggestion to the submitted domain, objective, impact, phase, and horizon.\n"
            "- Do not invent exact KPI values, client names, benchmarks, or DXC claims.\n"
            "- Suggest KPI names and ask for baseline and target values instead of fabricating them.\n"
            "- For short pitches such as 'improve mobile ux', propose measurable UX, conversion, adoption, support, or task-completion KPIs.\n"
            "- If the pitch implies customer experience but CustomerExperience is missing from impacts, suggest that reclassification explicitly.\n"
            "- Keep every suggestion specific, actionable, and fully written in English."
        ),
    },
    "tech_signals_enrichment": {
        "system": (
            "You are a technology sourcing analyst at DXC Technology.\n"
            "Your job is to classify web search results and keep ONLY real, "
            "concrete implementations — not articles or advice.\n"
            "Return ONLY valid JSON — no markdown, no preamble, no explanation."
        ),
        "user": (
            "Business need: {{pitch}}\n\n"
            "Web search results:\n"
            "{{numbered_results}}\n\n"
            "For each result, decide: is this a REAL implementation or an ARTICLE?\n\n"
            "A REAL implementation is:\n"
            "- A named software product, SaaS platform, or tool\n"
            "- A vendor or service provider with a concrete offering\n"
            "- A documented enterprise deployment with a named company and measurable outcome\n"
            "- An open-source project with a real GitHub repo or product page\n\n"
            "An ARTICLE is (exclude these):\n"
            "- Blog posts with tips or listicles\n"
            "- News coverage without a concrete product\n"
            "- Opinion pieces, guides, or how-to content\n\n"
            "Return a JSON array containing ONLY real implementations.\n"
            "Discard articles entirely — do not include them at all.\n\n"
            "Each object must have exactly these keys:\n"
            '{{"index": <int>, "signal_type": <saas_product|vendor|case_study|open_source>, '
            '"maturity_level": <emerging|growing|mature>, '
            '"insight": <one sentence max 25 words>}}\n\n'
            "If ALL results are articles, return []"
        ),
    },
}


@dataclass
class LLMResponse:
    """Structured response from the LLM provider."""

    content: str
    usage: dict[str, int]


def _get_langfuse_prompt(prompt_name: str, variables: dict[str, str]) -> tuple[str, str]:
    """Fetch a prompt from Langfuse, falling back to hardcoded defaults."""
    try:
        from langfuse import Langfuse

        lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        prompt = lf.get_prompt(prompt_name)
        compiled = prompt.compile(**variables)
        # Langfuse chat prompts return a list of messages
        if isinstance(compiled, list):
            system_msg = next((m["content"] for m in compiled if m["role"] == "system"), "")
            user_msg = next((m["content"] for m in compiled if m["role"] == "user"), "")
        else:
            # Langfuse text prompts return a single string
            system_msg, user_msg = "", str(compiled)

        # If the nlp_tagging prompt doesn't include suggestions, it's outdated — use the fallback
        if prompt_name == "nlp_tagging" and prompt_name in FALLBACK_PROMPTS:
            required_markers = (
                "suggestions",
                "objectif_confidence",
                "domaine_confidence",
                "gap_analysis_constraints",
                "intent explicite",
                "intent strategique DXC",
            )
            if any(marker not in user_msg for marker in required_markers):
                logger.warning(
                    "Langfuse prompt '%s' is missing the updated sourcing contract, using fallback",
                    prompt_name,
                )
                raise ValueError("outdated prompt")

        if prompt_name == "gap-analysis" and prompt_name in FALLBACK_PROMPTS:
            required_markers = (
                "Classification constraints",
                "Context compression",
                '"risks"',
            )
            if any(marker not in user_msg for marker in required_markers):
                logger.warning(
                    "Langfuse prompt '%s' is missing the updated qualification contract, using fallback",
                    prompt_name,
                )
                raise ValueError("outdated prompt")

        if prompt_name == "pitch-suggestions" and prompt_name in FALLBACK_PROMPTS:
            required_markers = (
                "Microsoft, SAP, ServiceNow, AWS, and ITIL",
                "Explicit intent",
                "Always respond in English",
                '"category"',
                '"action_type"',
                '"suggested_tags"',
            )
            if any(marker not in (system_msg + "\n" + user_msg) for marker in required_markers):
                logger.warning(
                    "Langfuse prompt '%s' is missing the updated DXC suggestions contract, using fallback",
                    prompt_name,
                )
                raise ValueError("outdated prompt")

        if prompt_name == "solution-recommendations-v2" and prompt_name in FALLBACK_PROMPTS:
            required_markers = (
                "Microsoft, SAP, ServiceNow, AWS and ITIL",
                '"related_feature_missing"',
                '"prerequisite_reason"',
                '"dxc_alignment"',
            )
            if any(marker not in (system_msg + "\n" + user_msg) for marker in required_markers):
                logger.warning(
                    "Langfuse prompt '%s' is missing the updated DXC delivery recommendations contract, using fallback",
                    prompt_name,
                )
                raise ValueError("outdated prompt")

        return system_msg, user_msg
    except Exception as exc:
        logger.warning("Langfuse unavailable (%s), using fallback prompt for '%s'", exc, prompt_name)
        fallback = FALLBACK_PROMPTS.get(prompt_name)
        if not fallback:
            raise ValueError(f"No fallback prompt defined for '{prompt_name}'") from exc
        system_text = fallback["system"]
        user_text = fallback["user"]
        for key, value in variables.items():
            user_text = user_text.replace("{{" + key + "}}", value)
            system_text = system_text.replace("{{" + key + "}}", value)
        return system_text, user_text


async def _complete_groq(system_prompt: str, user_prompt: str, response_format: str | None) -> LLMResponse:
    """Call Groq API with llama-3.3-70b-versatile."""
    from groq import AsyncGroq

    client = AsyncGroq(api_key=settings.groq_api_key)
    kwargs: dict = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    choice = response.choices[0]
    return LLMResponse(
        content=choice.message.content or "",
        usage={
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        },
    )


async def _complete_azure(system_prompt: str, user_prompt: str, response_format: str | None) -> LLMResponse:
    """Call Azure OpenAI with GPT-4o."""
    from openai import AsyncAzureOpenAI

    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )
    kwargs: dict = {
        "model": settings.azure_openai_deployment,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    choice = response.choices[0]
    return LLMResponse(
        content=choice.message.content or "",
        usage={
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        },
    )


async def complete(
    prompt_name: str,
    variables: dict[str, str],
    response_format: str | None = None,
) -> LLMResponse:
    """Unified LLM completion interface — dispatches to configured provider."""
    system_prompt, user_prompt = _get_langfuse_prompt(prompt_name, variables)

    if settings.llm_provider == "groq":
        return await _complete_groq(system_prompt, user_prompt, response_format)
    elif settings.llm_provider == "azure":
        return await _complete_azure(system_prompt, user_prompt, response_format)
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def parse_json_response(response: LLMResponse) -> dict:
    """Parse a JSON response from the LLM, stripping markdown fences if present."""
    content = response.content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])
    return json.loads(content)
