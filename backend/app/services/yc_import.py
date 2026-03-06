"""YC company import — mock fixture mode.

In production this would scrape the YC directory.
In mock mode it returns deterministic fixture data.
"""

from __future__ import annotations

from app.models.enums import LeadSource
from app.schemas.lead import LeadCreate

_YC_FIXTURES: list[dict] = [
    {
        "first_name": "Alice",
        "last_name": "Chen",
        "company_name": "DataForge AI",
        "company_domain": "dataforge.ai",
        "title": "CEO",
        "industry": "SaaS",
        "company_size": 25,
        "tech_stack": ["Python", "React", "PostgreSQL"],
    },
    {
        "first_name": "Bob",
        "last_name": "Martinez",
        "company_name": "ShipFast",
        "company_domain": "shipfast.dev",
        "title": "CTO",
        "industry": "Developer Tools",
        "company_size": 12,
        "tech_stack": ["Go", "TypeScript", "Kubernetes"],
    },
    {
        "first_name": "Carol",
        "last_name": "Nguyen",
        "company_name": "FinLedger",
        "company_domain": "finledger.io",
        "title": "Co-founder",
        "industry": "Fintech",
        "company_size": 8,
        "tech_stack": ["Rust", "React", "AWS"],
    },
    {
        "first_name": "David",
        "last_name": "Okafor",
        "company_name": "CloudPilot",
        "company_domain": "cloudpilot.com",
        "title": "CEO",
        "industry": "Infrastructure",
        "company_size": 30,
        "tech_stack": ["Python", "Terraform", "GCP"],
    },
    {
        "first_name": "Eva",
        "last_name": "Petrov",
        "company_name": "MediSync",
        "company_domain": "medisync.health",
        "title": "CEO",
        "industry": "Healthcare",
        "company_size": 15,
        "tech_stack": ["Python", "React", "AWS"],
    },
    {
        "first_name": "Frank",
        "last_name": "Kim",
        "company_name": "DevRelay",
        "company_domain": "devrelay.io",
        "title": "CTO",
        "industry": "Developer Tools",
        "company_size": 10,
        "tech_stack": ["TypeScript", "Node.js", "PostgreSQL"],
    },
    {
        "first_name": "Grace",
        "last_name": "Liu",
        "company_name": "SupplyAI",
        "company_domain": "supplyai.co",
        "title": "CEO",
        "industry": "Supply Chain",
        "company_size": 20,
        "tech_stack": ["Python", "Vue", "AWS"],
    },
    {
        "first_name": "Hassan",
        "last_name": "Ali",
        "company_name": "EduStack",
        "company_domain": "edustack.io",
        "title": "CEO",
        "industry": "EdTech",
        "company_size": 18,
        "tech_stack": ["Python", "Next.js", "PostgreSQL"],
    },
    {
        "first_name": "Iris",
        "last_name": "Tanaka",
        "company_name": "SecureNet",
        "company_domain": "securenet.dev",
        "title": "CTO",
        "industry": "Cybersecurity",
        "company_size": 35,
        "tech_stack": ["Rust", "Go", "Kubernetes"],
    },
    {
        "first_name": "Jack",
        "last_name": "Wilson",
        "company_name": "GreenOps",
        "company_domain": "greenops.earth",
        "title": "CEO",
        "industry": "Climate Tech",
        "company_size": 22,
        "tech_stack": ["Python", "React", "GCP"],
    },
]


async def import_yc_batch(
    batch: str = "W25",
    limit: int = 50,
) -> list[LeadCreate]:
    """Return mock YC company leads.

    In production, this would scrape the YC directory page
    for the given batch with rate limiting (1 req/2s).
    """
    fixtures = _YC_FIXTURES[:limit]
    return [
        LeadCreate(
            first_name=f["first_name"],
            last_name=f["last_name"],
            company_name=f["company_name"],
            company_domain=f["company_domain"],
            title=f["title"],
            industry=f["industry"],
            company_size=f["company_size"],
            tech_stack=f["tech_stack"],
            source=LeadSource.YC_SCRAPER,
        )
        for f in fixtures
    ]
