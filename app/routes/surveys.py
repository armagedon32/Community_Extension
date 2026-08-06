import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    PROJECT_CATEGORIES,
    DataCollectionSurvey,
    SurveyQuestion,
    SurveySubmission,
    SURVEY_STATUSES,
    QUESTION_TYPES,
)

surveys_bp = Blueprint("surveys", __name__)


def _normalize_survey(form):
    """Read survey header fields from a posted form, preserving omitted values."""
    return {
        "title": (request.form.get("title") or "").strip(),
        "category": request.form.get("category") or "Community Outreach",
        "description": (request.form.get("description") or "").strip(),
        "status": request.form.get("status") or "Active",
    }


def _save_questions(survey, form):
    """Replace a survey's questions from the dynamically submitted question rows."""
    SurveyQuestion.query.filter_by(survey_id=survey.id).delete()
    db.session.flush()
    q_texts = form.getlist("q_text")
    q_types = form.getlist("q_type")
    q_required = form.getlist("q_required")
    q_options = form.getlist("q_options")

    pos = 0
    for i, text in enumerate(q_texts):
        text = (text or "").strip()
        if not text:
            continue
        qtype = q_types[i] if i < len(q_types) else "scale"
        if qtype == "choice":
            options = (q_options[i] if i < len(q_options) else "").strip()
        else:
            options = None
        db.session.add(SurveyQuestion(
            survey_id=survey.id,
            question_text=text,
            question_type=qtype,
            required=(q_required[i] == "1") if i < len(q_required) else True,
            position=pos,
            options=options,
        ))
        pos += 1
    db.session.commit()


def _collect_answers(survey, form):
    """Build the answers JSON dict from a submission form."""
    answers = {}
    for question in survey.questions:
        value = form.get(f"q_{question.id}")
        if value is not None:
            value = str(value).strip()
            if question.question_type == "number" and value:
                try:
                    value = float(value)
                except ValueError:
                    value = None
            answers[str(question.id)] = value
    return answers


@surveys_bp.route("/surveys")
@login_required
def index():
    surveys = DataCollectionSurvey.query.order_by(DataCollectionSurvey.created_at.desc()).all()
    counts = {
        s.id: len(s.submissions) for s in surveys
    }
    return render_template(
        "surveys/index.html",
        surveys=surveys,
        counts=counts,
        SURVEY_STATUSES=SURVEY_STATUSES,
    )


@surveys_bp.route("/surveys/new", methods=["GET", "POST"])
@login_required
def new_survey():
    return _form(None)


@surveys_bp.route("/surveys/<int:survey_id>/edit", methods=["GET", "POST"])
@login_required
def edit_survey(survey_id):
    survey = db.get_or_404(DataCollectionSurvey, survey_id)
    return _form(survey)


@surveys_bp.route("/surveys/<int:survey_id>/delete", methods=["POST"])
@login_required
def delete_survey(survey_id):
    survey = db.get_or_404(DataCollectionSurvey, survey_id)
    if not current_user.has_role("Admin") and survey.created_by != current_user.id:
        flash("You are not authorized to delete this survey.", "danger")
        return redirect(url_for("surveys.index"))
    db.session.delete(survey)
    db.session.commit()
    flash("Survey template deleted.", "info")
    return redirect(url_for("surveys.index"))


@surveys_bp.route("/surveys/<int:survey_id>")
@login_required
def detail(survey_id):
    survey = db.get_or_404(DataCollectionSurvey, survey_id)
    submissions = survey.submissions

    # Gather numeric answers for scale/number questions to build charts
    scale_rows = []
    for question in survey.questions:
        if question.question_type == "text":
            continue
        values = []
        for sub in submissions:
            try:
                data = json.loads(sub.answers or "{}")
            except ValueError:
                continue
            v = data.get(str(question.id))
            if v is not None and v != "":
                try:
                    values.append(float(v))
                except (TypeError, ValueError):
                    continue
        if values:
            scale_rows.append({
                "label": question.question_text,
                "mean": round(sum(values) / len(values), 2),
                "count": len(values),
            })

    submissions_decoded = []
    locations = {}
    for sub in submissions:
        try:
            data = json.loads(sub.answers or "{}")
        except ValueError:
            data = {}
        submissions_decoded.append({"sub": sub, "data": data})
        if sub.location:
            locations[sub.location] = locations.get(sub.location, 0) + 1

    overall = None
    if scale_rows:
        overall = round(sum(r["mean"] for r in scale_rows) / len(scale_rows), 2)

    return render_template(
        "surveys/view.html",
        survey=survey,
        submissions=submissions,
        submissions_decoded=submissions_decoded,
        scale_rows=scale_rows,
        overall=overall,
        locations=locations,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
    )


@surveys_bp.route("/surveys/<int:survey_id>/collect")
@login_required
def collect(survey_id):
    survey = db.get_or_404(DataCollectionSurvey, survey_id)
    if survey.status == "Closed":
        flash("This survey is closed for data collection.", "warning")
        return redirect(url_for("surveys.detail", survey_id=survey.id))
    return render_template("surveys/collect.html", survey=survey)


@surveys_bp.route("/surveys/<int:survey_id>/submit", methods=["POST"])
@login_required
def submit(survey_id):
    survey = db.get_or_404(DataCollectionSurvey, survey_id)
    answers = _collect_answers(survey, request.form)
    submission = SurveySubmission(
        survey_id=survey.id,
        respondent_name=(request.form.get("respondent_name") or "").strip(),
        location=(request.form.get("location") or "").strip(),
        contact=(request.form.get("contact") or "").strip(),
        submitted_by=current_user.id,
        answers=json.dumps(answers),
    )
    db.session.add(submission)
    db.session.commit()
    flash("Data collection record saved successfully.", "success")
    return redirect(url_for("surveys.detail", survey_id=survey.id))


@surveys_bp.route("/surveys/<int:survey_id>/submissions/<int:sub_id>/delete", methods=["POST"])
@login_required
def delete_submission(survey_id, sub_id):
    sub = db.get_or_404(SurveySubmission, sub_id)
    db.session.delete(sub)
    db.session.commit()
    flash("Submission deleted.", "info")
    return redirect(url_for("surveys.detail", survey_id=survey_id))


def _form(survey):
    if request.method == "POST":
        data = _normalize_survey(request)
        if not data["title"]:
            flash("Survey title is required.", "danger")
            return render_template("surveys/form.html", survey=survey, PROJECT_CATEGORIES=PROJECT_CATEGORIES, QUESTION_TYPES=QUESTION_TYPES, SURVEY_STATUSES=SURVEY_STATUSES)
        if survey is None:
            survey = DataCollectionSurvey(
                title=data["title"],
                category=data["category"],
                description=data["description"],
                status=data["status"],
                created_by=current_user.id,
            )
            db.session.add(survey)
            db.session.commit()
            _save_questions(survey, request.form)
            flash("Survey template created.", "success")
            return redirect(url_for("surveys.detail", survey_id=survey.id))
        else:
            survey.title = data["title"]
            survey.category = data["category"]
            survey.description = data["description"]
            survey.status = data["status"]
            db.session.commit()
            _save_questions(survey, request.form)
            flash("Survey template updated.", "success")
            return redirect(url_for("surveys.detail", survey_id=survey.id))

    return render_template(
        "surveys/form.html",
        survey=survey,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
        QUESTION_TYPES=QUESTION_TYPES,
        SURVEY_STATUSES=SURVEY_STATUSES,
    )