"""AI-driven Outcome-Based Evaluation (transparent, proposal-aligned).

For every approved extension project (status ``Ongoing`` or ``Completed``),
this module rates the expected outcomes as **Low**, **Medium**, or **High**
by comparing the actual project results against the **expected deliverables
and measurable targets recorded for that specific approved proposal**.

Every indicator exposes:

- the **expected target** recorded from the approved proposal (with the
  deliverable/outcome it represents); when none is recorded, a documented
  default benchmark is used instead,
- the **actual result** read from CELMIS data,
- the **attainment** (actual / target), and
- the **classification criterion** applied to assign Low / Medium / High.

Attainment is mapped to a 0-100 score (100 = fully met or exceeded the
target). The overall rating is the equal-weighted average of the applicable
indicator scores::

    Low    -> average score <  50  (achieved < 50% of targets on average)
    Medium -> 50 <= average <  80  (achieved 50% - 79% of targets)
    High   -> average >= 80        (achieved >= 80% of targets)

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

# Indicators used by the evaluation. ``default_target`` and
# ``default_basis`` apply only when the approved proposal has no recorded
# target for the indicator.
INDICATOR_DEFS = {
    "deliverable_completion": {
        "name": "Deliverable Completion",
        "description": (
            "Progress toward the expected deliverables stated in the approved "
            "proposal, as encoded by the project leader."
        ),
        "dataset": "projects.progress (0-100)",
        "unit": "percent",
        "unit_label": "%",
        "default_target": 100.0,
        "default_basis": "Complete all expected deliverables stated in the approved proposal.",
    },
    "deliverable_documentation": {
        "name": "Deliverable Documentation",
        "description": (
            "Number of accomplishment reports submitted as documented evidence "
            "that the proposal's expected deliverables and outcomes were achieved."
        ),
        "dataset": "accomplishment_reports (count by project)",
        "unit": "count",
        "unit_label": "report(s)",
        "default_target": 2.0,
        "default_basis": "Submit at least one documented accomplishment report per expected deliverable.",
    },
    "activity_implementation": {
        "name": "Activity Implementation",
        "description": (
            "Share of planned activities actually implemented (Completed or "
            "Ongoing) out of all scheduled activities for the project."
        ),
        "dataset": "activities (status by project)",
        "unit": "percent",
        "unit_label": "%",
        "default_target": 100.0,
        "default_basis": "Implement all planned activities described in the approved proposal.",
    },
    "beneficiary_reach": {
        "name": "Beneficiary Reach",
        "description": (
            "Number of beneficiaries actually served, as documented in the "
            "accomplishment reports for the project."
        ),
        "dataset": "accomplishment_reports.beneficiaries_served (sum by project)",
        "unit": "count",
        "unit_label": "beneficiaries",
        "default_target": 50.0,
        "default_basis": "Reach the target number of beneficiaries set in the approved proposal.",
    },
    "budget_utilization": {
        "name": "Budget Utilization",
        "description": (
            "Approved funds utilized (Expense and Allocation) relative to the "
            "budget stated in the approved proposal."
        ),
        "dataset": "financial_transactions (Approved) / projects.budget",
        "unit": "percent",
        "unit_label": "%",
        "default_target": 80.0,
        "default_basis": "Utilize at least 80% of the approved proposal budget.",
    },
}

INDICATOR_KEYS = list(INDICATOR_DEFS.keys())

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


def _display_value(value, unit):
    if unit == "amount":
        return f"₱{value:,.0f}"
    if unit == "percent":
        return f"{value:g}%"
    return f"{value:g}"


def _target_display(target):
    if target is None:
        return None
    return _display_value(target.target_value, target.unit or "count")


def _metrics(project):
    """Return the raw measured value for every indicator of one project."""
    progress = max(0, min(int(project.progress or 0), 100))
    reports = list(project.accomplishments)
    activities = list(project.activities)

    total_activities = len(activities)
    implemented = sum(1 for a in activities if a.status in ("Ongoing", "Completed"))
    implemented_pct = (implemented / total_activities) * 100 if total_activities else 0.0

    served = sum(_num(ac.beneficiaries_served) for ac in reports)

    budget = _num(project.budget)
    spent = 0.0
    for t in FinancialTransaction.query.filter_by(
        project_id=project.id, status="Approved"
    ).all():
        if t.transaction_type in _SPENT_TYPES:
            spent += _num(t.amount)
    util_pct = (spent / budget) * 100 if budget > 0 else None

    return {
        "deliverable_completion": progress,
        "deliverable_documentation": float(len(reports)),
        "activity_implementation": implemented_pct if total_activities else 0.0,
        "beneficiary_reach": served,
        "budget_utilization": util_pct,
    }


def _actual_display(key, measure, project):
    if key == "deliverable_completion":
        return f"{measure:g}%"
    if key == "deliverable_documentation":
        return f"{measure:g} report(s)"
    if key == "activity_implementation":
        activities = list(project.activities)
        if not activities:
            return "None scheduled"
        implemented = sum(1 for a in activities if a.status in ("Ongoing", "Completed"))
        return f"{implemented} / {len(activities)} activities ({measure:.0f}%)"
    if key == "beneficiary_reach":
        return f"{measure:,.0f} served"
    if key == "budget_utilization":
        budget = _num(project.budget)
        if budget <= 0:
            return "No approved budget on record"
        spent = 0.0
        for t in FinancialTransaction.query.filter_by(
            project_id=project.id, status="Approved"
        ).all():
            if t.transaction_type in _SPENT_TYPES:
                spent += _num(t.amount)
        return f"{measure:.1f}% (₱{spent:,.0f} / ₱{budget:,.0f})"
    return str(measure)


def _criterion(level, target_display, has_target):
    middle = "the target of " if has_target else "the default benchmark of "
    return {
        "Low": f"actual result below 50% of {middle}{target_display}",
        "Medium": f"actual result 50% - 79% of {middle}{target_display}",
        "High": f"actual result at least 80% of {middle}{target_display}",
    }[level]


def _indicators(project):
    """Compute the proposal-aligned indicators for one project."""
    metrics = _metrics(project)
    targets = {t.indicator_key: t for t in project.targets}

    indicators = []
    for key in INDICATOR_KEYS:
        definition = INDICATOR_DEFS[key]
        measure = metrics[key]

        # Budget utilization is not measurable without an approved budget.
        applicable = True
        if key == "budget_utilization" and measure is None:
            applicable = False

        target = targets.get(key)
        has_target = target is not None and target.target_value > 0
        target_value = (float(target.target_value) if has_target else
                        definition["default_target"])
        target_display = (target.target_value if has_target else
                          definition["default_target"])
        target_label = _display_value(target_display, definition["unit"])
        target_basis = (target.basis or definition["default_basis"]) if has_target else definition["default_basis"]

        if not applicable:
            score = 0.0
            attainment = None
            attainment_display = "—"
            level = "Low"
            basis = (
                f"The approved proposal has no budget amount, so utilization cannot "
                f"be measured; this indicator is excluded from the overall score."
            )
        else:
            if target_value > 0 and measure is not None:
                attainment = measure / target_value
            else:
                attainment = 0.0
            attainment_display = f"{attainment * 100:.0f}%"
            score = round(min(attainment, 1.0) * 100, 1)
            level = _level(score)
            criterion_text = _criterion(level, target_label, has_target)
            if has_target:
                basis = (
                    f"Expected from proposal: {target_basis} "
                    f"(target: {target_label}). Actual: {_actual_display(key, measure, project)}. "
                    f"Attainment {attainment_display} [{criterion_text}]."
                )
            else:
                basis = (
                    f"No target recorded for this proposal, so the default benchmark "
                    f"({target_label}) was used. Actual: {_actual_display(key, measure, project)}. "
                    f"Attainment {attainment_display} [{criterion_text}]."
                )

        indicators.append({
            "key": key,
            "name": definition["name"],
            "description": definition["description"],
            "dataset": definition["dataset"],
            "has_target": has_target,
            "target_value": target_display,
            "target_display": target_label,
            "target_basis": target_basis if has_target else None,
            "criteria_label": target_label,
            "value": measure,
            "display": _actual_display(key, measure, project) if applicable else "—",
            "attainment": attainment,
            "attainment_display": attainment_display,
            "score": score,
            "level": level,
            "level_class": LEVEL_CLASS[level],
            "basis": basis,
            "applicable": applicable,
        })

    return indicators


def evaluate_project(project):
    """Compute the full outcome evaluation for a single project.

    The result carries the rating, the equal-weighted overall score, the
    per-indicator breakdown (expected target, actual result, attainment,
    criterion, and basis), and the dataset consulted.
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
         "purpose": "Planned vs implemented activities",
         "records": len(project.activities)},
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

    targets = [
        {
            "key": t.indicator_key,
            "name": t.indicator_name,
            "target_display": _display_value(t.target_value, t.unit or "count"),
            "basis": t.basis,
        }
        for t in sorted(project.targets, key=lambda x: x.indicator_key)
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
        "targets": targets,
        "targets_count": len(targets),
        "targets_total": len(INDICATOR_KEYS),
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