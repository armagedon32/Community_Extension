from datetime import datetime
import io

from docx import Document as DocxDocument
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.ml.engine import classify_domain
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
    "Community Outreach": [
        "community outreach", "community needs", "outreach program",
        "community extension", "community service", "community development",
        "community engagement", "community project", "barangay outreach",
        "needs assessment", "community assessment", "community consultation",
        "extension program", "extension project", "extension services",
        "community support", "community aid", "community relief",
        "community benefit", "community impact", "social responsibility",
        "beneficiary", "beneficiaries", "stakeholder", "partnership",
        "collaboration", "stakeholders engagement", "public service",
        "social development", "community welfare", "community program",
        "extension activity", "extension initiative", "volunteerism",
        "volunteer program", "community immersion", "community participation",
        "resource mobilization", "capacity building", "grassroots",
        "sectoral", "multi-sectoral", "linkages", "linkage program",
    ],
    "Health": [
        "health", "medical", "clinic", "nutrition", "doctor", "nurse",
        "immunization", "screening", "hygiene", "diabetes", "feeding",
        "hospital", "patient", "wellness", "disease", "vaccine",
        "check-up", "check up", "dental", "maternal", "childbirth",
        "pregnancy", "mental health", "sanitation", "first aid",
        "blood pressure", "BMI", "treatment", "medicine", "therapy",
        "health program", "health outreach", "health mission",
        "family planning", "reproductive health", "child health",
        "adolescent health", "senior citizen health", "nutrition program",
        "feeding program", "medical mission", "health caravan",
        "health education", "health awareness", "health promotion",
        "preventive health", "curative health", "rehabilitation",
        "substance abuse", "communicable disease", "non-communicable",
        "TB", "malaria", "dengue", "COVID", "pandemic", "epidemic",
        "health worker", "barangay health", "rural health",
        "health facility", "health center", "barangay health station",
    ],
    "Livelihood": [
        "livelihood", "income", "business", "skills training",
        "entrepreneurship", "starter kit", "market", "micro",
        "employment", "training", "cooperative", "selling",
        "profit", "revenue", "financial", "savings", "loan",
        "products", "handicraft", "soap", "food processing",
        "veggie", "farming", "agriculture", "harvest",
        "self-employment", "self employment", "job creation",
        "job placement", "career", "vocational", "technical skills",
        "wage", "salary", "income generation", "microfinance",
        "micro-enterprise", "micro enterprise", "small business",
        "medium enterprise", "SME", "start-up", "startup",
        "product development", "market access", "value chain",
        "supply chain", "raw materials", "production",
        "manufacturing", "processing", "packaging", "labeling",
        "quality control", "pricing", "marketing", "sales",
        "financial literacy", "bookkeeping", "accounting",
        "sustainable livelihood", "economic development",
    ],
    "Education": [
        "literacy", "reading", "teacher", "teaching", "learning",
        "tuition", "scholarship", "school", "learner", "tutorial",
        "education", "student", "classroom", "deped", "academic",
        "seminar", "workshop", "lecture", "course",
        "enrollment", "graduation", "diploma", "training program",
        "elementary", "secondary", "tertiary", "college",
        "university", "faculty", "instructor", "professor",
        "curriculum", "instruction", "pedagogy", "andragogy",
        "assessment", "evaluation", "grading", "examination",
        "test", "quiz", "assignment", "project", "research",
        "thesis", "dissertation", "capstone", "practicum",
        "internship", "on-the-job training", "OJT",
        "academic calendar", "semester", "term", "enrollee",
        "graduate", "alumni", "alumna", "alumnus",
        "scholar", "scholarship", "grant", "financial aid",
        "educational support", "learning materials", "textbook",
        "module", "e-learning", "distance learning", "online class",
        "tutorial program", "remedial", "remediation",
    ],
    "Environment": [
        "coastal", "cleanup", "tree", "planting", "riverbank", "bamboo",
        "environment", "seedling", "forest", "water access", "garden",
        "recycling", "waste", "ecology", "conservation", "organic",
        "composting", "clean and green", "eco", "sustainability",
        "climate", "renewable", "solar", "water purification",
        "environmental", "ecosystem", "biodiversity", "wildlife",
        "habitat", "natural resources", "natural resource",
        "land use", "land management", "soil conservation",
        "air quality", "water quality", "pollution control",
        "solid waste", "liquid waste", "hazardous waste",
        "segregation", "recycling program", "zero waste",
        "refuse", "reduce", "reuse", "recycle",
        "renewable energy", "solar energy", "wind energy",
        "energy conservation", "energy efficiency",
        "climate change", "global warming", "greenhouse gas",
        "carbon footprint", "carbon emission",
        "reforestation", "afforestation", "deforestation",
        "watershed", "river", "creek", "lake", "ocean",
        "marine", "coastal", "mangrove", "coral reef",
        "flood control", "drainage", "irrigation",
    ],
    "Governance": [
        "municipal", "government", "council", "provincial", "governance",
        "local government", "barangay council", "policy", "legislation",
        "public administration", "transparency", "accountability",
        "ordinance", "resolution", "official", "public service",
        "citizen", "community participation", "stakeholder engagement",
        "barangay", "municipality", "city", "province", "region",
        "LGU", "DILG", "DILG", "department of interior",
        "local governance", "good governance", "clean governance",
        "anti-corruption", "anti-corruption", "right to information",
        "freedom of information", "public disclosure",
        "participatory governance", "people empowerment",
        "barangay development", "local development",
        "public-private partnership", "PPP",
        "government project", "government program",
        "public hearing", "consultation meeting",
        "legislative", "executive", "judicial",
        "executive order", "memorandum", "circular",
        "compliance", "regulation", "standard", "protocol",
    ],
    "Technology": [
        "computer", "digital", "technology", "internet", "software",
        "tesda", "technical", "coding", "programming", "system",
        "ICT", "information technology", "web", "mobile app",
        "data", "online", "e-learning", "LMS", "robotics",
        "STEM", "innovation", "automation",
        "hardware", "network", "server", "database",
        "cloud", "cloud computing", "cybersecurity",
        "artificial intelligence", "AI", "machine learning",
        "data science", "analytics", "big data",
        "internet of things", "IoT", "blockchain",
        "virtual reality", "VR", "augmented reality", "AR",
        "3D printing", "drone", "unmanned",
        "digital literacy", "digital transformation",
        "e-government", "e-governance", "e-commerce",
        "digital marketing", "social media", "SEO",
        "website", "web development", "app development",
        "software development", "IT training",
        "computer literacy", "basic computer",
        "word processing", "spreadsheet", "presentation",
        "graphic design", "video editing", "photo editing",
    ],
}


def _extract_text_from_docx(file_storage):
    """Extract text from an uploaded .docx file."""
    file_bytes = file_storage.read()
    file_storage.seek(0)
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _keyword_predict(text):
    """Fallback keyword-based category prediction with title weighting."""
    lines = text.split("\n")
    header = "\n".join(lines[:5]).lower() if lines else ""
    t = text.lower()

    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        count = 0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in t:
                count += 1
            if kw_lower in header:
                count += 5
        if count > 0:
            scores[category] = count

    if scores:
        return max(scores, key=scores.get)
    return CATEGORY_FALLBACK


def _extract_project_title(text):
    """Extract project title from document if explicitly labeled."""
    import re
    patterns = [
        r"(?:project\s*title|title\s*of\s*project)[:\s]+(.+)",
        r"(?:project\s*name)[:\s]+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _predict_category(text):
    """Predict project category using ML model with keyword fallback."""
    lines = text.split("\n")
    header = "\n".join(lines[:5]).lower() if lines else ""

    project_title = _extract_project_title(text)
    search_text = (project_title + " " + header).lower() if project_title else header

    for cat in CATEGORY_KEYWORDS:
        if cat.lower() in search_text:
            return cat

    predicted, scores = classify_domain(text)

    if predicted and predicted in PROJECT_CATEGORIES:
        confidence = scores.get(predicted, 0)
        if confidence >= 30:
            return predicted

    keyword_result = _keyword_predict(text)
    return keyword_result


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