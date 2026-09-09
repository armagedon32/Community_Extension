"""Efficiency Comparison routes.

Records and compares the actual processing time, record retrieval time,
report-generation time, and other applicable efficiency indicators between the
existing manual procedure and the developed system.

The page presents the measured manual and system-based results together with
the computed time difference and percentage improvement. The ISO/IEC 25010
perceived performance-efficiency results are shown separately as user
-perception data (never as the sole basis for a drastic turnaround-time claim).
"""
from datetime import date
from statistics import mean

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    EfficiencyIndicator,
    EfficiencyMeasurement,
    EfficiencyPerception,
    EfficiencyPerceptionResponse,
)

efficiency_bp = Blueprint("efficiency", __name__)

_LIKERT_LABELS = {
    1: "Strongly Disagree",
    2: "Disagree",
    3: "Neutral",
    4: "Agree",
    5: "Strongly Agree",
}

# Interpretation thresholds for the mean perceived rating (1-5 Likert).
_PERCEPTION_LEVELS = [
    (1.81, "Very Low", "danger"),
    (2.61, "Low", "warning"),
    (3.41, "Neutral", "secondary"),
    (4.21, "High", "info"),
    (5.01, "Very High", "success"),
]


def _fmt(seconds):
    """Human-readable rendering of a duration given in seconds."""
    if seconds is None:
        return "—"
    seconds = round(seconds, 1)
    if seconds >= 60:
        mins = int(seconds // 60)
        secs = seconds - mins * 60
        return f"{mins}m {secs:g}s" if secs else f"{mins}m"
    return f"{seconds:g}s"


def _perception_level(avg):
    for threshold, level, cls in _PERCEPTION_LEVELS:
        if avg is not None and avg < threshold:
            return level, cls
    return "—", "secondary"


def _build_context():
    """Compute the objective comparison rows and the perception aggregates."""
    rows = []
    for ind in EfficiencyIndicator.query.order_by(EfficiencyIndicator.sort_order, EfficiencyIndicator.id).all():
        manual = [m.duration_seconds for m in ind.measurements if m.method == "Manual"]
        system = [m.duration_seconds for m in ind.measurements if m.method == "System"]
        manual_avg = mean(manual) if manual else None
        system_avg = mean(system) if system else None

        pct = None
        verdict, verdict_class = "Incomplete data", "secondary"
        if manual_avg is not None and system_avg is not None and manual_avg > 0:
            pct = (manual_avg - system_avg) / manual_avg * 100
            if pct >= 5:
                verdict, verdict_class = "Improved", "success"
            elif pct <= -5:
                verdict, verdict_class = "Slower", "danger"
            else:
                verdict, verdict_class = "Comparable", "secondary"

        difference_seconds = (manual_avg - system_avg) if (manual_avg is not None and system_avg is not None) else None
        difference_text = None
        if difference_seconds is not None:
            if difference_seconds > 0:
                difference_text = f"{_fmt(difference_seconds)} faster"
            elif difference_seconds < 0:
                difference_text = f"{_fmt(-difference_seconds)} slower"
            else:
                difference_text = "No difference"

        rows.append({
            "indicator": ind,
            "manual_count": len(manual),
            "manual_avg": manual_avg,
            "manual_display": f"{_fmt(manual_avg)} (n={len(manual)})" if manual_avg is not None else "—",
            "system_count": len(system),
            "system_avg": system_avg,
            "system_display": f"{_fmt(system_avg)} (n={len(system)})" if system_avg is not None else "—",
            "pct": pct,
            "pct_display": f"{pct:+.1f}%" if pct is not None else "—",
            "difference_seconds": difference_seconds,
            "difference_text": difference_text,
            "verdict": verdict,
            "verdict_class": verdict_class,
            "measurements": ind.measurements,
        })

    evaluated = [r for r in rows if r["pct"] is not None]
    avg_improvement = mean(r["pct"] for r in evaluated) if evaluated else None

    perceptions = []
    for p in EfficiencyPerception.query.order_by(EfficiencyPerception.id).all():
        ratings = [r.rating for r in p.responses]
        n = len(ratings)
        avg = mean(ratings) if n else None
        level, cls = _perception_level(avg)
        perceptions.append({
            "perception": p,
            "n": n,
            "mean": avg,
            "mean_display": f"{avg:.2f}" if avg is not None else "—",
            "distribution": {i: ratings.count(i) for i in range(1, 6)},
            "level": level,
            "level_class": cls,
            "responses": p.responses,
        })

    all_ratings = []
    for p in EfficiencyPerception.query.all():
        all_ratings.extend(r.rating for r in p.responses)
    perception_overall_mean = mean(all_ratings) if all_ratings else None
    perception_level, perception_level_class = _perception_level(perception_overall_mean)

    return {
        "rows": rows,
        "evaluated_count": len(evaluated),
        "avg_improvement": avg_improvement,
        "avg_improvement_display": f"{avg_improvement:+.1f}%" if avg_improvement is not None else "—",
        "total_measurements": EfficiencyMeasurement.query.count(),
        "manual_trials": EfficiencyMeasurement.query.filter_by(method="Manual").count(),
        "system_trials": EfficiencyMeasurement.query.filter_by(method="System").count(),
        "perceptions": perceptions,
        "perception_statements": len(perceptions),
        "perception_responses": len(all_ratings),
        "perception_overall_mean": perception_overall_mean,
        "perception_overall_display": (
            f"{perception_overall_mean:.2f} / 5.00" if perception_overall_mean is not None else "—"),
        "perception_overall_level": perception_level,
        "perception_overall_class": perception_level_class,
        "likert_labels": _LIKERT_LABELS,
        "methods": ["Manual", "System"],
        "computed_at": date.today(),
    }


@efficiency_bp.route("/efficiency")
@login_required
def index():
    ctx = _build_context()
    return render_template("efficiency/index.html", **ctx)


@efficiency_bp.route("/efficiency/indicator/save", methods=["POST"])
@login_required
def save_indicator():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Indicator name is required.", "danger")
        return redirect(url_for("efficiency.index"))
    indicator_id = request.form.get("indicator_id")
    try:
        sort_order = int(request.form.get("sort_order") or 0)
    except ValueError:
        sort_order = 0
    existing = db.session.get(EfficiencyIndicator, int(indicator_id)) if indicator_id else None
    if existing:
        existing.name = name
        existing.description = request.form.get("description", "").strip() or None
        existing.unit = request.form.get("unit", "").strip() or "seconds"
        existing.sort_order = sort_order
        flash(f"Indicator \"{name}\" updated.", "success")
    else:
        db.session.add(EfficiencyIndicator(
            name=name,
            description=request.form.get("description", "").strip() or None,
            unit=request.form.get("unit", "").strip() or "seconds",
            sort_order=sort_order,
        ))
        flash(f"Indicator \"{name}\" added.", "success")
    db.session.commit()
    return redirect(url_for("efficiency.index"))


@efficiency_bp.route("/efficiency/indicator/<int:indicator_id>/delete", methods=["POST"])
@login_required
def delete_indicator(indicator_id):
    ind = db.session.get(EfficiencyIndicator, indicator_id)
    if ind:
        name = ind.name
        db.session.delete(ind)
        db.session.commit()
        flash(f"Indicator \"{name}\" and its trials were deleted.", "warning")
    return redirect(url_for("efficiency.index"))


@efficiency_bp.route("/efficiency/indicator/<int:indicator_id>/measurement", methods=["POST"])
@login_required
def save_measurement(indicator_id):
    ind = db.session.get(EfficiencyIndicator, indicator_id)
    if not ind:
        flash("Indicator not found.", "danger")
        return redirect(url_for("efficiency.index"))

    method = request.form.get("method", "Manual")
    if method not in ("Manual", "System"):
        method = "Manual"
    try:
        minutes = float(request.form.get("minutes") or 0)
        seconds = float(request.form.get("seconds") or 0)
    except ValueError:
        minutes = seconds = 0
    duration_seconds = max(0.0, minutes * 60 + seconds)
    if duration_seconds <= 0:
        flash("Duration must be greater than zero.", "danger")
        return redirect(url_for("efficiency.index"))

    measured_on_raw = request.form.get("measured_on", "").strip()
    try:
        measured_on = date.fromisoformat(measured_on_raw) if measured_on_raw else date.today()
    except ValueError:
        measured_on = date.today()

    db.session.add(EfficiencyMeasurement(
        indicator_id=ind.id,
        method=method,
        duration_seconds=duration_seconds,
        measured_on=measured_on,
        measured_by=current_user.full_name if current_user.is_authenticated else None,
        notes=request.form.get("notes", "").strip() or None,
    ))
    db.session.commit()
    flash(f"Timed trial added for \"{ind.name}\" ({method}).", "success")
    return redirect(url_for("efficiency.index"))


@efficiency_bp.route("/efficiency/measurement/<int:measurement_id>/delete", methods=["POST"])
@login_required
def delete_measurement(measurement_id):
    m = db.session.get(EfficiencyMeasurement, measurement_id)
    if m:
        db.session.delete(m)
        db.session.commit()
        flash("Timed trial deleted.", "warning")
    return redirect(url_for("efficiency.index"))


@efficiency_bp.route("/efficiency/perception/save", methods=["POST"])
@login_required
def save_perception():
    statement = request.form.get("statement", "").strip()
    if not statement:
        flash("Perception statement is required.", "danger")
        return redirect(url_for("efficiency.index"))
    perception_id = request.form.get("perception_id")
    existing = db.session.get(EfficiencyPerception, int(perception_id)) if perception_id else None
    if existing:
        existing.statement = statement
        existing.dimension = request.form.get("dimension", "").strip() or \
            "ISO/IEC 25010 Performance Efficiency (Perceived)"
        flash("Perception statement updated.", "success")
    else:
        db.session.add(EfficiencyPerception(
            statement=statement,
            dimension=request.form.get("dimension", "").strip() or
            "ISO/IEC 25010 Performance Efficiency (Perceived)",
        ))
        flash("Perception statement added.", "success")
    db.session.commit()
    return redirect(url_for("efficiency.index"))


@efficiency_bp.route("/efficiency/perception/<int:perception_id>/response", methods=["POST"])
@login_required
def record_perception(perception_id):
    """Record individual Likert responses (1-5) for a perception statement.

    Accepts counts per scale value (``rating_1`` ... ``rating_5``) and stores
    one ``EfficiencyPerceptionResponse`` row per counted respondent, so the raw
    respondent-level data is preserved and auditable.
    """
    p = db.session.get(EfficiencyPerception, perception_id)
    if not p:
        flash("Perception statement not found.", "danger")
        return redirect(url_for("efficiency.index"))

    added = 0
    for rating in range(1, 6):
        raw = request.form.get(f"rating_{rating}", "").strip()
        if not raw:
            continue
        try:
            count = int(raw)
        except ValueError:
            count = 0
        for _ in range(max(0, min(count, 500))):
            db.session.add(EfficiencyPerceptionResponse(
                perception_id=p.id,
                rating=rating,
                respondent=request.form.get("respondent", "").strip() or None,
            ))
            added += 1
    db.session.commit()
    flash(f"{added} perception rating(s) recorded.", "success" if added else "info")
    return redirect(url_for("efficiency.index"))


@efficiency_bp.route("/efficiency/perception/<int:perception_id>/response/<int:response_id>/delete", methods=["POST"])
@login_required
def delete_response(perception_id, response_id):
    r = db.session.get(EfficiencyPerceptionResponse, response_id)
    if r and r.perception_id == perception_id:
        db.session.delete(r)
        db.session.commit()
        flash("Perception rating deleted.", "warning")
    return redirect(url_for("efficiency.index"))


@efficiency_bp.route("/efficiency/perception/<int:perception_id>/delete", methods=["POST"])
@login_required
def delete_perception(perception_id):
    p = db.session.get(EfficiencyPerception, perception_id)
    if p:
        db.session.delete(p)
        db.session.commit()
        flash("Perception statement deleted.", "warning")
    return redirect(url_for("efficiency.index"))