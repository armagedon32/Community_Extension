from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models import (
    ACTIVITY_STATUSES,
    BENEFICIARY_SEGMENTS,
    MOA,
    PARTNER_TYPES,
    Activity,
    Beneficiary,
    Partner,
    Project,
    PROJECT_CATEGORIES,
    PROJECT_STATUSES,
    ROLES,
)

dashboard_bp = Blueprint("dashboard", __name__)


def _group_count(model, column, allowed):
    dist = {k: 0 for k in allowed}
    rows = db.session.query(column, func.count(model.id)).group_by(column).all()
    for key, count in rows:
        if key in dist:
            dist[key] = count
    return dist


@dashboard_bp.route("/")
@login_required
def index():
    total_projects = Project.query.count()
    total_partners = Partner.query.count()
    total_beneficiaries = Beneficiary.query.count()
    total_activities = Activity.query.count()
    total_moas = MOA.query.count()

    status_dist = _group_count(Project, Project.status, PROJECT_STATUSES)
    category_dist = _group_count(Project, Project.category, PROJECT_CATEGORIES)
    beneficiary_segments = _group_count(Beneficiary, Beneficiary.segment, BENEFICIARY_SEGMENTS)
    partner_types = _group_count(Partner, Partner.partner_type, PARTNER_TYPES)
    activity_status_dist = _group_count(Activity, Activity.status, ACTIVITY_STATUSES)

    total_budget = 0.0
    for p in Project.query.all():
        try:
            total_budget += float(p.budget or 0)
        except (TypeError, ValueError):
            pass

    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
    recent_activities = Activity.query.order_by(Activity.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard/index.html",
        total_projects=total_projects,
        total_partners=total_partners,
        total_beneficiaries=total_beneficiaries,
        total_activities=total_activities,
        total_moas=total_moas,
        projects_proposed=status_dist.get("Proposed", 0),
        projects_active=status_dist.get("Ongoing", 0),
        projects_completed=status_dist.get("Completed", 0),
        status_dist=status_dist,
        category_dist=category_dist,
        beneficiary_segments=beneficiary_segments,
        partner_types=partner_types,
        activity_status_dist=activity_status_dist,
        recent_projects=recent_projects,
        recent_activities=recent_activities,
        total_budget=total_budget,
        PROJECT_STATUSES=PROJECT_STATUSES,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
        ROLES=ROLES,
    )