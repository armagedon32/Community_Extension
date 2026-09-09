"""AI-driven Outcome-Based Evaluation (transparent, indicator-based).

For every approved extension project (status ``Ongoing`` or ``Completed``),
this module rates the expected outcomes as **Low**, **Medium**, or **High**
by scoring measurable indicators derived from the deliverables and outcomes
stated in the approved proposal. Every indicator exposes:

- the **data source** it reads from (which CELMIS tables/fields feed it),
- the exact **thresholds** used to assign each rating level,
- the observed **value** and the **basis** used for the classification.

The overall rating is the equal-weighted average of the applicable indicator
scores (on a 0-100 scale), mapped with clearly defined breakpoints::

    Low    -> average score <  50
    Medium -> 50 <= average score <  80
    High   -> average score >= 80

Everything is computed live from the recorded data so the assessment stays
measurable, transparent, and aligned with the approved proposal.
"""
from datetime import datetime

from app.models import FinancialTransaction, Project

RATING_LEVELS = ["Low", "Medium", "High"]

# Overall classification breakpoints (score, 0-100): (min, max)
LEVEL_BREAKPOINTS = {
    "Low": (0, 50),
    "Medium": (50, 80),
    "High": (80, 101),
}

LEVEL_CLASS = {
    "Low": "danger",
    "Medium": "warning",
    "High": "success",
}

# Indicators that are read when the evaluated project has no approved budget.
_SPENT_TYPES = ("Expense", "Allocation")


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _level(score):
    if score >= 80:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def _score_basis(score, level, condition):
    """Human-readable basis text for one indicator classification."""
    return (
        f"Observed score {round(score, 1)}/100. "
        f"Meets the {level.upper()} threshold ({condition})."
    )


def _indicators(project):
    """Compute the measurable indicators for one project.

    Each indicator is returned with its definition, data source, the
    thresholds applied for every rating level, the observed value, the
    0-100 score, the assigned level, and the basis of the classification.
    """
    progress = max(0, min(int(project.progress or 0), 100))
    reports = list(project.accomplishments)
    activities = list(project.activities)

    total_activities = len(activities)
    implemented = sum(
        1 for a in activities if a.status in ("Ongoing", "Completed")
    )

    served = sum(_num(ac.beneficiaries_served) for ac in reports)

    budget = _num(project.budget)
    spent = 0.0
    for t in FinancialTransaction.query.filter_by(
        project_id=project.id, status="Approved"
    ).all():
        if t.transaction_type in _SPENT_TYPES:
            spent += _num(t.amount)

    ind = []

    # ---- 1. Deliverable Completion -------------------------------------
    ind.append({
        "key": "deliverable_completion",
        "name": "Deliverable Completion",
        "description": (
            "Progress toward the expected deliverables stated in the approved "
            "proposal, as encoded by the project leader."
        ),
        "dataset": "projects.progress (0-100)",
        "criteria": [
            {"level": "Low", "condition": "progress < 50%"},
            {"level": "Medium", "condition": "progress 50% - 79%"},
            {"level": "High", "condition": "progress >= 80%"},
        ],
        "value": progress,
        "display": f"{progress}%",
        "score": progress,
        "level": _level(progress),
        "basis": _score_basis(progress, _level(progress),
                              _display_condition(_level(progress),
                                                 "progress < 50%",
                                                 "progress 50% - 79%",
                                                 "progress >= 80%")),
        "applicable": True,
    })

    # ---- 2. Deliverable Documentation -----------------------------------
    n_docs = len(reports)
    score_docs = min(n_docs / 2.0, 1.0) * 100
    ind.append({
        "key": "deliverable_documentation",
        "name": "Deliverable Documentation",
        "description": (
            "Number of accomplishment reports submitted as documented evidence "
            "that the proposal's expected deliverables and outcomes were achieved."
        ),
        "dataset": "accomplishment_reports (count by project)",
        "criteria": [
            {"level": "Low", "condition": "0 reports"},
            {"level": "Medium", "condition": "1 report"},
            {"level": "High", "condition": ">= 2 reports"},
        ],
        "value": n_docs,
        "display": f"{n_docs} report(s)",
        "score": round(score_docs, 1),
        "level": _level(score_docs),
        "basis": _score_basis(score_docs, _level(score_docs),
                              _display_condition(_level(score_docs),
                                                 "0 reports",
                                                 "1 report",
                                                 ">= 2 reports")),
        "applicable": True,
    })

    # ---- 3. Activity Implementation -------------------------------------
    if total_activities == 0:
        score_act = 0.0
        impl_display = "None scheduled"
        impl_basis = (
            "No planned activities are recorded for this project, so "
            "implementation cannot be evidenced yet."
        )
        impl_level = "Low"
    else:
        ratio = implemented / total_activities
        score_act = ratio * 100
        impl_display = f"{implemented} / {total_activities} activities ({ratio * 100:.0f}%)"
        impl_level = _level(score_act)
        impl_basis = _score_basis(score_act, impl_level,
                                  _display_condition(impl_level,
                                                     "less than 50% implemented",
                                                     "50% - 79% implemented",
                                                     ">= 80% implemented"))
    ind.append({
        "key": "activity_implementation",
        "name": "Activity Implementation",
        "description": (
            "Share of planned activities actually implemented (Completed or "
            "Ongoing) out of all scheduled activities for the project."
        ),
        "dataset": "activities (status by project)",
        "criteria": [
            {"level": "Low", "condition": "< 50% of activities implemented"},
            {"level": "Medium", "condition": "50% - 79% of activities implemented"},
            {"level": "High", "condition": ">= 80% of activities implemented"},
        ],
        "value": None if total_activities == 0 else round(ratio * 100, 1),
        "display": impl_display,
        "score": round(score_act, 1),
        "level": impl_level,
        "basis": impl_basis,
        "applicable": True,
    })

    # ---- 4. Beneficiary Reach -------------------------------------------
    score_reach = min(served / 50.0, 1.0) * 100
    ind.append({
        "key": "beneficiary_reach",
        "name": "Beneficiary Reach",
        "description": (
            "Number of beneficiaries actually served, as documented in the "
            "accomplishment reports for the project."
        ),
        "dataset": "accomplishment_reports.beneficiaries_served (sum by project)",
        "criteria": [
            {"level": "Low", "condition": "0 beneficiaries served"},
            {"level": "Medium", "condition": "1 - 49 beneficiaries served"},
            {"level": "High", "condition": ">= 50 beneficiaries served"},
        ],
        "value": served,
        "display": f"{served:,.0f} served",
        "score": round(score_reach, 1),
        "level": _level(score_reach),
        "basis": _score_basis(score_reach, _level(score_reach),
                              _display_condition(_level(score_reach),
                                                 "0 beneficiaries served",
                                                 "1 - 49 beneficiaries served",
                                                 ">= 50 beneficiaries served")),
        "applicable": True,
    })

    # ---- 5. Budget Utilization ------------------------------------------
    budget_applicable = budget > 0
    if budget_applicable:
        util = spent / budget
        score_budget = min(util / 0.8, 1.0) * 100
        util_pct = min(util * 100, 999)
        budget_display = (
            f"{util_pct:.1f}% (₱{spent:,.0f} / ₱{budget:,.0f})"
        )
        budget_basis = _score_basis(score_budget, _level(score_budget),
                                    _display_condition(_level(score_budget),
                                                       "less than 50% of budget used",
                                                       "50% - 79% of budget used",
                                                       ">= 80% of budget used"))
    else:
        score_budget = 0.0
        budget_display = "No approved budget on record"
        budget_basis = (
            "The approved proposal has no budget amount, so utilization cannot "
            "be measured; this indicator is excluded from the overall score."
        )

    ind.append({
        "key": "budget_utilization",
        "name": "Budget Utilization",
        "description": (
            "Approved funds utilized (Expense and Allocation) relative to the "
            "budget stated in the approved proposal."
        ),
        "dataset": "financial_transactions (Approved) / projects.budget",
        "criteria": [
            {"level": "Low", "condition": "< 50% of budget utilized"},
            {"level": "Medium", "condition": "50% - 79% of budget utilized"},
            {"level": "High", "condition": ">= 80% of budget utilized"},
        ],
        "value": None if not budget_applicable else round(util * 100, 1),
        "display": budget_display,
        "score": round(score_budget, 1),
        "level": _level(score_budget) if budget_applicable else "Low",
        "basis": budget_basis,
        "applicable": budget_applicable,
    })

    return ind


def _display_condition(level, low, medium, high):
    return {"Low": low, "Medium": medium, "High": high}[level]


def evaluate_project(project):
    """Compute the full outcome evaluation for a single project.

    The result carries the rating, the equal-weighted overall score, the
    per-indicator breakdown, the dataset consulted, and the proposal it is
    aligned with, so the classification is fully auditable.
    """
    indicators = _indicators(project)
    applicable = [i for i in indicators if i["applicable"]]
    overall = round(
        sum(i["score"] for i in applicable) / len(applicable), 1
    ) if applicable else 0.0
    rating = _level(overall) if project.status in ("Ongoing", "Completed") else None

    finance_count = FinancialTransaction.query.filter_by(
        project_id=project.id
    ).count()

    dataset = [
        {"source": "projects.progress", "purpose": "Deliverable completion", "records": 1},
        {"source": "activities",
         "purpose": "Planned vs implemented activities", "records": len(project.activities)},
        {"source": "accomplishment_reports",
         "purpose": "Deliverable evidence and beneficiaries served",
         "records": len(project.accomplishments)},
        {"source": "beneficiaries",
         "purpose": "Registered beneficiaries", "records": len(project.beneficiaries)},
        {"source": "financial_transactions (Approved)",
         "purpose": "Budget utilization", "records": finance_count},
        {"source": "moas", "purpose": "Formal partnership alignment", "records": len(project.moas)},
        {"source": "mous", "purpose": "Partnership intent alignment", "records": len(project.mous)},
    ]

    return {
        "project": project,
        "approved": project.status in ("Ongoing", "Completed"),
        "overall_score": overall,
        "rating": rating,
        "rating_class": LEVEL_CLASS.get(rating, "secondary"),
        "indicator_count": len(applicable),
        "indicators": indicators,
        "dataset": dataset,
        "breakpoints": LEVEL_BREAKPOINTS,
        "computed_at": datetime.utcnow(),
    }


def evaluate_all():
    """Evaluate every project and return a portfolio summary.

    Only approved projects (Ongoing/Completed) are scored; Proposed projects
    are still pending approval and are excluded from the rating, but their
    count is reported for transparency.
    """
    projects = (
        Project.query.filter(Project.status.in_(["Ongoing", "Completed"]))
        .order_by(Project.updated_at.desc())
        .all()
    )
    evaluations = [evaluate_project(p) for p in projects]

    dist = {"Low": 0, "Medium": 0, "High": 0}
    scores = []
    for e in evaluations:
        if e["rating"]:
            dist[e["rating"]] += 1
            scores.append(e["overall_score"])

    proposed = Project.query.filter_by(status="Proposed").count()

    return {
        "evaluations": evaluations,
        "dist": dist,
        "total_evaluated": len(evaluations),
        "excluded_proposed": proposed,
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "computed_at": datetime.utcnow(),
        "breakpoints": LEVEL_BREAKPOINTS,
    }