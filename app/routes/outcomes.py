"""AI-driven Outcome-Based Evaluation routes.

Surfaces the indicator-based outcome ratings (Low / Medium / High) computed
by ``app.ml.outcomes`` for approved extension projects. Both views expose the
dataset, the measurable indicators, the classification criteria, and the
basis used, keeping the AI-generated assessment transparent and auditable.
"""
from datetime import datetime

from flask import Blueprint, render_template
from flask_login import login_required

from app.ml.outcomes import LEVEL_BREAKPOINTS, RATING_LEVELS, evaluate_all, evaluate_project
from app.models import Project

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