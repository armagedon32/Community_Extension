from sqlalchemy import func

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    EVALUATION_CHARACTERISTICS,
    EvaluationItem,
    EvaluationResponse,
)

evals_bp = Blueprint("evaluations", __name__)

# Default ISO/IEC 25010 questionnaire items per characteristic.
DEFAULT_ITEMS = {
    "Functional Suitability": [
        "The system provides all essential features for managing community extension programs.",
        "The classification results are accurate and appropriate.",
        "The system generates complete and correct analytics and reports.",
        "All core processes function as intended.",
    ],
    "Performance Efficiency": [
        "The system loads and responds quickly.",
        "The system remains responsive during simultaneous processes.",
        "The system shortens the time required to process documents and reports.",
        "System outputs are generated promptly.",
    ],
    "Compatibility": [
        "The system works properly on different devices (desktop, laptop, tablet).",
        "The system functions across various browsers and operating systems.",
        "The system interface displays correctly on all supported platforms.",
    ],
    "Usability": [
        "The system is easy to learn for first-time users.",
        "Navigation and layout are clear and user-friendly.",
        "Instructions, buttons, and labels are easy to understand.",
        "Users can efficiently complete tasks.",
    ],
    "Reliability": [
        "The system operates smoothly without crashing or interruption.",
        "The system performs consistently even during heavy use.",
        "Data is stored and retrieved accurately.",
        "The system produces consistent results.",
    ],
    "Security": [
        "User data is protected from unauthorized access.",
        "Login authentication and account management are secure.",
        "Sensitive data is securely stored and transmitted.",
    ],
    "Maintainability": [
        "The system's code and architecture are organized and easy to update.",
        "Components are modular, allowing efficient maintenance.",
        "Errors can be fixed without disrupting other functionalities.",
        "Documentation is sufficient for ongoing maintenance.",
    ],
    "Safety": [
        "The system maintains data integrity and prevents errors.",
        "The system protects against risks associated with incorrect data handling.",
        "System operations do not cause harm or disadvantage to stakeholders.",
    ],
}


def _ensure_items():
    try:
        existing = EvaluationItem.query.count()
    except Exception:
        existing = 0
    if existing > 0:
        return
    for char, indicators in DEFAULT_ITEMS.items():
        for indicator in indicators:
            db.session.add(EvaluationItem(characteristic=char, indicator=indicator))
    db.session.commit()


@evals_bp.route("/evaluations/questionnaire", methods=["GET", "POST"])
@login_required
def questionnaire():
    _ensure_items()
    items = EvaluationItem.query.order_by(EvaluationItem.characteristic).all()

    if request.method == "POST":
        existing = EvaluationResponse.query.filter_by(user_id=current_user.id).first()
        if existing:
            EvaluationResponse.query.filter_by(user_id=current_user.id).delete()
        count = 0
        for item in items:
            val = request.form.get(f"score_{item.id}")
            if val in {"1", "2", "3", "4", "5"}:
                db.session.add(EvaluationResponse(
                    item_id=item.id,
                    user_id=current_user.id,
                    score=int(val),
                ))
                count += 1
        db.session.commit()
        if count:
            flash(f"Evaluation submitted successfully ({count} responses).", "success")
        else:
            flash("No responses were submitted.", "warning")
        return redirect(url_for("evaluations.results"))

    grouped = {c: [] for c in EVALUATION_CHARACTERISTICS}
    for item in items:
        grouped[item.characteristic].append(item)
    return render_template("evaluations/questionnaire.html", grouped=grouped)


@evals_bp.route("/evaluations")
@login_required
def results():
    _ensure_items()
    items = EvaluationItem.query.all()
    stats = {}
    for item in items:
        item_stats = {
            "responses": EvaluationResponse.query.filter_by(item_id=item.id).count(),
            "mean": None,
        }
        mean = db.session.query(func.avg(EvaluationResponse.score)).filter(
            EvaluationResponse.item_id == item.id
        ).scalar()
        item_stats["mean"] = round(float(mean), 2) if mean is not None else None
        stats[item.id] = item_stats

    characteristic_means = {}
    for char in EVALUATION_CHARACTERISTICS:
        responses = (
            db.session.query(EvaluationResponse.score)
            .join(EvaluationItem)
            .filter(EvaluationItem.characteristic == char)
            .all()
        )
        if responses:
            characteristic_means[char] = round(
                sum(r[0] for r in responses) / len(responses), 2
            )
        else:
            characteristic_means[char] = None

    item_rows = EvaluationItem.query.order_by(EvaluationItem.characteristic).all()
    evaluator_count = db.session.query(func.count(func.distinct(EvaluationResponse.user_id))).scalar() or 0

    overall = None
    all_means = [m for m in characteristic_means.values() if m is not None]
    if all_means:
        overall = round(sum(all_means) / len(all_means), 2)

    return render_template(
        "evaluations/results.html",
        items=item_rows,
        stats=stats,
        characteristic_means=characteristic_means,
        evaluator_count=evaluator_count,
        overall=overall,
    )


@evals_bp.route("/evaluations/clear", methods=["POST"])
@login_required
def clear():
    if not current_user.has_role("Admin"):
        flash("Only administrators can clear evaluation data.", "danger")
        return redirect(url_for("evaluations.results"))
    EvaluationResponse.query.delete()
    db.session.commit()
    flash("All evaluation responses cleared.", "info")
    return redirect(url_for("evaluations.results"))