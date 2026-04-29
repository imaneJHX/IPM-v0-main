"""Static DXC staffing profiles used by qualification scoring."""

from __future__ import annotations

from typing import Final

DXC_PROFILES: Final[list[dict[str, object]]] = [
    {
        "id": "data-scientist",
        "name": "Data Scientist",
        "skills": ["python", "machine learning", "prediction", "nlp", "statistics", "modeling"],
        "seniority_level": "senior",
        "daily_capacity": 2,
        "typical_tasks": [
            "design predictive models",
            "analyze business data",
            "evaluate model performance",
        ],
    },
    {
        "id": "ai-engineer",
        "name": "AI Engineer",
        "skills": ["llm", "genai", "prompting", "mlops", "rag", "ai integration"],
        "seniority_level": "senior",
        "daily_capacity": 3,
        "typical_tasks": [
            "industrialize AI services",
            "deploy inference pipelines",
            "integrate AI into enterprise applications",
        ],
    },
    {
        "id": "cloud-architect",
        "name": "Cloud Architect",
        "skills": ["cloud", "azure", "aws", "architecture", "integration", "networking"],
        "seniority_level": "senior",
        "daily_capacity": 2,
        "typical_tasks": [
            "define target architecture",
            "design cloud landing zones",
            "secure integration patterns",
        ],
    },
    {
        "id": "devops-engineer",
        "name": "DevOps Engineer",
        "skills": ["ci/cd", "containers", "kubernetes", "automation", "monitoring", "terraform"],
        "seniority_level": "mid",
        "daily_capacity": 3,
        "typical_tasks": [
            "automate deployments",
            "manage runtime environments",
            "set up observability pipelines",
        ],
    },
    {
        "id": "business-analyst",
        "name": "Business Analyst",
        "skills": ["requirements", "process mapping", "stakeholder management", "kpi", "functional analysis"],
        "seniority_level": "mid",
        "daily_capacity": 4,
        "typical_tasks": [
            "translate business needs into requirements",
            "clarify user journeys",
            "define measurable outcomes",
        ],
    },
    {
        "id": "ux-ui-designer",
        "name": "UX/UI Designer",
        "skills": ["ux", "ui", "journey", "wireframe", "prototype", "accessibility"],
        "seniority_level": "mid",
        "daily_capacity": 2,
        "typical_tasks": [
            "design service journeys",
            "prototype interfaces",
            "improve usability and adoption",
        ],
    },
    {
        "id": "cybersecurity-expert",
        "name": "Cybersecurity Expert",
        "skills": ["security", "compliance", "privacy", "iam", "audit", "risk"],
        "seniority_level": "senior",
        "daily_capacity": 2,
        "typical_tasks": [
            "review security controls",
            "validate compliance requirements",
            "define protection and monitoring measures",
        ],
    },
]

DXC_PROFILES_BY_ID: Final[dict[str, dict[str, object]]] = {
    str(profile["id"]): profile
    for profile in DXC_PROFILES
}
