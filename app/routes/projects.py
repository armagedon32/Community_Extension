from datetime import datetime
import io

from docx import Document as DocxDocument
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    AccomplishmentReport,
    Beneficiary,
    MOA,
    Project,
    PROJECT_CATEGORIES,
    PROJECT_STATUSES,
    User,
)

projects_bp = Blueprint("projects", __name__)

CATEGORY_FALLBACK = "Community Outreach"

CATEGORY_KEYWORDS = {
    "Health": ["health", "medical", "clinic", "nutrition", "doctor", "nurse",
               "immunization", "screening", "hygiene", "diabetes", "feeding",
               "hospital", "patient", "wellness", "disease", "vaccine"],
    "Livelihood": ["livelihood", "income", "soap", "business", "skills training",
                   "entrepreneurship", "starter kit", "market", "micro", "jobs",
                   "employment", "training", "skills", "cooperative"],
    "Education": ["literacy", "reading", "teacher", "teaching", "learning", "tuition",
                  "scholarship", "school", "learner", "tutorial", "education",
                  "student", "classroom", "deped", "academic"],
    "Environment": ["coastal", "cleanup", "tree", "plant", "riverbank", "bamboo",
                    "environment", "seedling", "forest", "water access", "garden",
                    "recycling", "waste", "ecology", "conservation"],
    "Governance": ["municipal", "government", "council", "provincial", "governance",
                   "local government", "barangay council", "policy", "legislation",
                   "public administration", "transparency"],
    "Technology": ["computer", "digital", "technology", "internet", "software",
                   "tesda", "technical", "coding", "programming", "IT", "system"],
}


def _extract_text_from_docx(file_storage):
    """Extract text from an uploaded .docx file."""
    file_bytes = file_storage.read()
    file_storage.seek(0)
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _predict_category(text):
    """Predict project category from text using keyword matching."""
    t = text.lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in t)
        if count > 0:
            scores[category] = count

    if scores:
        best = max(scores, key=scores.get)
        return best
    return CATEGORY_FALLBACK


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@projects_bp.route("/projects/predict-category", methods=["POST"])
@login_required
def predict_category():
    file = request.files.get("document")
    if not file:
        return jsonify({"error": "No file uploaded."}), 400
    filename = (file.filename or "").lower()
    if not filename.endswith(".docx"):
        return jsonify({"error": "Only .docx files are supported."}), 400
    try:
        text = _extract_text_from_docx(file)
        if not text.strip():
            return jsonify({"error": "Document is empty or unreadable."}), 400
        category = _predict_category(text)
        return jsonify({"category": category})
    except Exception as e:
        return jsonify({"error": f"Failed to process document: {str(e)}"}), 500


@projects_bp.route("/projects")
@login_required
def list_projects():
    query = Project.query
    category = request.args.get("category", "")
    status = request.args.get("status", "")

    if category and category in PROJECT_CATEGORIES:
        query = query.filter(Project.category == category)
    if status and status in PROJECT_STATUSES:
        query = query.filter(Project.status == status)

    projects = query.order_by(Project.created_at.desc()).all()
    return render_template(
        "projects/list.html",
        projects=projects,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
        PROJECT_STATUSES=PROJECT_STATUSES,
        current_category=category,
        current_status=status,
    )


@projects_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def create_project():
    leaders = User.query.order_by(User.full_name).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Project title is required.", "danger")
            return render_template("projects/form.html", project=None, leaders=leaders,
                                   PROJECT_CATEGORIES=PROJECT_CATEGORIES,
                                   PROJECT_STATUSES=PROJECT_STATUSES, is_edit=False)

        category = request.form.get("category", "Community Outreach")

        file = request.files.get("document")
        if file and (file.filename or "").lower().endswith(".docx"):
            try:
                text = _extract_text_from_docx(file)
                if text.strip():
                    category = _predict_category(text)
            except Exception:
                pass

        project = Project(
            title=title,
            category=category,
            description=request.form.get("description", ""),
            status=request.form.get("status", "Proposed"),
            leader_id=request.form.get("leader_id") or None,
            start_date=_parse_date(request.form.get("start_date")),
            end_date=_parse_date(request.form.get("end_date")),
            progress=int(request.form.get("progress", 0) or 0),
            budget=request.form.get("budget", 0) or 0,
            location=request.form.get("location", ""),
        )
        db.session.add(project)
        db.session.commit()
        flash("Project created successfully.", "success")
        return redirect(url_for("projects.list_projects"))

    return render_template("projects/form.html", project=None, PROJECT_CATEGORIES=PROJECT_CATEGORIES,
                           PROJECT_STATUSES=PROJECT_STATUSES, is_edit=False, leaders=leaders)


@projects_bp.route("/projects/<int:project_id>")
@login_required
def view_project(project_id):
    project = db.get_or_404(Project, project_id)
    beneficiaries = Beneficiary.query.filter_by(project_id=project.id).all()
    moas = MOA.query.filter_by(project_id=project.id).all()
    reports = AccomplishmentReport.query.filter_by(project_id=project.id).all()
    progress_values = list(range(0, 101, 5))
    return render_template(
        "projects/view.html",
        project=project,
        beneficiaries=beneficiaries,
        moas=moas,
        reports=reports,
        progress_values=progress_values,
    )


@projects_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    project = db.get_or_404(Project, project_id)
    leaders = User.query.order_by(User.full_name).all()
    if request.method == "POST":
        project.title = request.form.get("title", project.title).strip()
        project.category = request.form.get("category", project.category)
        project.description = request.form.get("description", project.description)
        project.status = request.form.get("status", project.status)
        project.leader_id = request.form.get("leader_id") or None
        project.start_date = _parse_date(request.form.get("start_date"))
        project.end_date = _parse_date(request.form.get("end_date"))
        try:
            project.progress = int(request.form.get("progress", project.progress) or 0)
        except ValueError:
            pass
        project.budget = request.form.get("budget", project.budget) or 0
        project.location = request.form.get("location", project.location)
        db.session.commit()
        flash("Project updated successfully.", "success")
        return redirect(url_for("projects.view_project", project_id=project.id))

    return render_template("projects/form.html", project=project, PROJECT_CATEGORIES=PROJECT_CATEGORIES,
                           PROJECT_STATUSES=PROJECT_STATUSES, is_edit=True, leaders=leaders)


@projects_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    project = db.get_or_404(Project, project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted successfully.", "info")
    return redirect(url_for("projects.list_projects"))