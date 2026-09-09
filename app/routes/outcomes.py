"""AI-driven Outcome-Based Evaluation routes.

Surfaces the indicator-based outcome ratings (Low / Medium / High) computed
by ``app.ml.outcomes`` for approved extension projects. Both views expose the
dataset, the measurable indicators, the classification criteria, and the
basis used, keeping the AI-generated assessment transparent and auditable.

Also lets the institution record the expected deliverables and measurable
targets of each approved proposal, which become the basis of the indicators.
"""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.ml.outcomes import INDICATOR_DEFS, INDICATOR_KEYS, LEVEL_BREAKPOINTS, RATING_LEVELS, evaluate_all, evaluate_project
from app.models import Project, ProjectTarget

outcomes_bp = Blueprint("outcomes", __name__)

_LEVEL_CLASS = {
    "Low": "danger",
    "Medium": "warning",
    "High": "success",
}


@outcomes_bp.route("/outcomes")
@login_required
def index():
    data = evaluate_all()
    return render_template(
        "outcomes/index.html",
        data=data,
        rating_levels=RATING_LEVELS,
        level_class=_LEVEL_CLASS,
        breakpoints=LEVEL_BREAKPOINTS,
    )


@outcomes_bp.route("/outcomes/<int:project_id>")
@login_required
def detail(project_id):
    project = Project.query.get_or_404(project_id)
    evaluation = evaluate_project(project)
    return render_template(
        "outcomes/detail.html",
        evaluation=evaluation,
        breakpoints=LEVEL_BREAKPOINTS,
        level_class=_LEVEL_CLASS,
        computed_at=datetime.utcnow(),
    )


@outcomes_bp.route("/outcomes/<int:project_id>/targets", methods=["GET", "POST"])
@login_required
def targets(project_id):
    """Record or edit the expected deliverables and measurable targets."""
    project = Project.query.get_or_404(project_id)

    if request.method == "POST":
        recorded = 0
        for key in INDICATOR_KEYS:
            raw = request.form.get(f"target_{key}", "").strip().replace(",", "")
            basis = request.form.get(f"basis_{key}", "").strip()
            existing = ProjectTarget.query.filter_by(
                project_id=project.id, indicator_key=key
            ).first()

            if raw:
                try:
                    value = float(raw)
                except ValueError:
                    value = 0.0
                if value > 0:
                    definition = INDICATOR_DEFS[key]
                    if existing:
                        existing.target_value = value
                        existing.basis = basis or None
                    else:
                        db.session.add(ProjectTarget(
                            project_id=project.id,
                            indicator_key=key,
                            indicator_name=definition["name"],
                            target_value=value,
                            unit=definition["unit"],
                            basis=basis or None,
                        ))
                    recorded += 1
                    continue
            if existing:
                db.session.delete(existing)
        db.session.commit()
        flash(f"Expected deliverables and targets saved ({recorded} indicator(s)).", "success")
        return redirect(url_for("outcomes.detail", project_id=project.id))

    records = {t.indicator_key: t for t in project.targets}
    return render_template(
        "outcomes/targets.html",
        project=project,
        indicator_defs=INDICATOR_DEFS,
        records=records,
        computed_at=datetime.utcnow(),
    )