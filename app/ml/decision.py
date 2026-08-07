"""AI Decision Support and Recommendation system.

Gates the current extension-portfolio state and produces data-driven
recommendations. It examines portfolio balance (category coverage, budget
distribution), beneficiary reach, institutional linkages, and ML readiness,
then turns the findings into prioritized, actionable suggestions that support
institutional decision-making and study objectives.
"""
from app.ml import engine
from app.models import (
    BENEFICIARY_SEGMENTS,
    MOA,
    PARTNER_TYPES,
    PROJECT_CATEGORIES,
    PROJECT_STATUSES,
    Beneficiary,
    Partner,
    Project,
)


def _count(model, column, value):
    return model.query.filter(getattr(model, column) == value).count()


def _sum_budget():
    total = 0.0
    for p in Project.query.all():
        try:
            total += float(p.budget or 0)
        except (TypeError, ValueError):
            continue
    return total


def build_recommendations():
    """Compute portfolio analytics and generate prioritized recommendations."""
    total_projects = Project.query.count()
    total_budget = _sum_budget()
    total_beneficiaries = Beneficiary.query.count()
    total_partners = Partner.query.count()

    cat_dist = {c: _count(Project, "category", c) for c in PROJECT_CATEGORIES}
    seg_dist = {s: _count(Beneficiary, "segment", s) for s in BENEFICIARY_SEGMENTS}
    part_dist = {p: _count(Partner, "partner_type", p) for p in PARTNER_TYPES}

    ml_ready = engine.load_model("type")[0] is not None

    recommendations = []

    # 1. No data yet
    if total_projects == 0:
        recommendations.append({
            "priority": "High",
            "category": "Data Foundation",
            "title": "Register portfolio data",
            "detail": ("No projects are registered yet. Add projects, partners, beneficiaries, and activities "
                       "so analytics, reporting, and AI classification can be used."),
        })

    # 2. Category coverage
    if total_projects > 0:
        covered = [c for c, n in cat_dist.items() if n > 0]
        uncovered = [c for c, n in cat_dist.items() if n == 0]
        if len(covered) == 1:
            recommendations.append({
                "priority": "Medium",
                "category": "Portfolio Balance",
                "title": f"Portfolio concentrated in {covered[0]}",
                "detail": ("All extension efforts fall under one category. Expanding into other categories would "
                           "broaden impact and reduce reliance on a single theme."),
            })
        elif uncovered:
            recommendations.append({
                "priority": "Medium",
                "category": "Portfolio Balance",
                "title": f"Unserved category: {uncovered[0]}",
                "detail": (f"No project addresses {uncovered[0]}. Developing a new initiative here would improve "
                           "category coverage in the portfolio."),
            })
        else:
            recommendations.append({
                "priority": "Low",
                "category": "Portfolio Balance",
                "title": "Portfolio is well spread",
                "detail": "Projects span multiple categories, indicating a balanced extension strategy.",
            })

    # 3. Budget focus
    if total_budget > 0 and cat_dist:
        top_cat, top_n = max(cat_dist.items(), key=lambda kv: kv[1])
        recommendations.append({
            "priority": "Low",
            "category": "Resource Allocation",
            "title": f"Budget priority: {top_cat}",
            "detail": (f"The leading category is {top_cat} with {top_n} project(s). Ensure budget supports these "
                       "initiatives and monitor cost per category for efficiency."),
        })

    # 4. Beneficiary reach
    if total_beneficiaries == 0:
        recommendations.append({
            "priority": "High",
            "category": "Beneficiary Reach",
            "title": "No beneficiaries recorded",
            "detail": "Record beneficiaries reached per project so reach and engagement can be measured.",
        })
    else:
        served_segs = [s for s, n in seg_dist.items() if n > 0]
        if len(served_segs) < len(BENEFICIARY_SEGMENTS):
            underserved = [s for s, n in seg_dist.items() if n == 0]
            recommendations.append({
                "priority": "Medium",
                "category": "Beneficiary Reach",
                "title": f"Underserved segment: {underserved[0]}",
                "detail": (f"No beneficiaries are recorded for {underserved[0]}. Targeting this group could "
                           "maximize social inclusion and reach."),
            })

    # 5. Institutional linkage depth
    if total_partners == 0:
        recommendations.append({
            "priority": "High",
            "category": "Institutional Linkages",
            "title": "Establish partner organizations",
            "detail": "No partner organizations. Partnerships expand resources and strengthen the linkage program.",
        })
    else:
        linkage_types = [p for p, n in part_dist.items() if n > 0]
        if len(linkage_types) < len(PARTNER_TYPES):
            recommendations.append({
                "priority": "Medium",
                "category": "Institutional Linkages",
                "title": "Diversify partner types",
                "detail": "Partners are concentrated in a few types. Engage other sectors to widen institutional linkages.",
            })

    # 6. ML readiness
    if not ml_ready:
        recommendations.append({
            "priority": "Medium",
            "category": "AI Readiness",
            "title": "Train the classification model",
            "detail": "Add labeled documents and train the Naive Bayes model so automatic classification and NLP features work.",
        })

    # 7. Monitoring note
    recommendations.append({
        "priority": "Low",
        "category": "Monitoring",
        "title": "Monitor progress and accounts",
        "detail": "Keep project progress and finance records current so the decision-support view stays accurate and auditable.",
    })

    return {
        "total_projects": total_projects,
        "total_budget": total_budget,
        "total_beneficiaries": total_beneficiaries,
        "total_partners": total_partners,
        "cat_dist": cat_dist,
        "seg_dist": seg_dist,
        "part_dist": part_dist,
        "ml_ready": ml_ready,
        "recommendations": recommendations,
    }