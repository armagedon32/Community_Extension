from datetime import date, timedelta

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models import (
    ACTIVITY_STATUSES,
    BENEFICIARY_SEGMENTS,
    MOA,
    MOA_STATUSES,
    MOU,
    MOU_STATUSES,
    PARTNER_TYPES,
    AccomplishmentReport,
    Activity,
    Beneficiary,
    DataCollectionSurvey,
    Partner,
    Project,
    PROJECT_CATEGORIES,
    PROJECT_STATUSES,
)

dashboard_bp = Blueprint("dashboard", __name__)


def _group_count(model, column, allowed):
    dist = {k: 0 for k in allowed}
    rows = db.session.query(column, func.count(model.id)).group_by(column).all()
    for key, count in rows:
        if key in dist:
            dist[key] = count
    return dist


def _group_by(model, column):
    dist = {}
    rows = db.session.query(column, func.count(model.id)).group_by(column).all()
    for key, count in rows:
        if key is not None:
            dist[key] = count
    return dist


@dashboard_bp.route("/")
@login_required
def index():
    """Community Extension Dashboard — projects, activities, beneficiaries, monitoring."""
    total_projects = Project.query.count()
    total_activities = Activity.query.count()
    total_beneficiaries = Beneficiary.query.count()
    total_accomplishments = AccomplishmentReport.query.count()

    beneficiaries_served = (
        db.session.query(func.coalesce(func.sum(AccomplishmentReport.beneficiaries_served), 0)).scalar() or 0
    )

    total_budget = 0.0
    for p in Project.query.all():
        try:
            total_budget += float(p.budget or 0)
        except (TypeError, ValueError):
            pass

    status_dist = _group_count(Project, Project.status, PROJECT_STATUSES)
    category_dist = _group_count(Project, Project.category, PROJECT_CATEGORIES)
    beneficiary_segments = _group_count(Beneficiary, Beneficiary.segment, BENEFICIARY_SEGMENTS)
    activity_status_dist = _group_count(Activity, Activity.status, ACTIVITY_STATUSES)

    today = date.today()
    upcoming_activities = (
        Activity.query.filter(Activity.schedule_date >= today, Activity.status == "Scheduled")
        .order_by(Activity.schedule_date.asc())
        .limit(5)
        .all()
    )
    upcoming_count = (
        Activity.query.filter(Activity.schedule_date >= today, Activity.status == "Scheduled").count()
    )

    total_surveys = DataCollectionSurvey.query.count()

    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
    recent_activities = Activity.query.order_by(Activity.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard/index.html",
        total_projects=total_projects,
        total_activities=total_activities,
        total_beneficiaries=total_beneficiaries,
        total_accomplishments=total_accomplishments,
        beneficiaries_served=float(beneficiaries_served or 0),
        total_budget=total_budget,
        projects_proposed=status_dist.get("Proposed", 0),
        projects_active=status_dist.get("Ongoing", 0),
        projects_completed=status_dist.get("Completed", 0),
        status_dist=status_dist,
        category_dist=category_dist,
        beneficiary_segments=beneficiary_segments,
        activity_status_dist=activity_status_dist,
        upcoming_activities=upcoming_activities,
        upcoming_count=upcoming_count,
        total_surveys=total_surveys,
        recent_projects=recent_projects,
        recent_activities=recent_activities,
        PROJECT_STATUSES=PROJECT_STATUSES,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
    )


@dashboard_bp.route("/linkages")
@login_required
def linkages():
    """Institutional Linkages Dashboard — partners, MOAs, MOUs, partnership monitoring."""
    total_partners = Partner.query.count()
    active_partners = Partner.query.filter_by(status="Active").count()
    total_moas = MOA.query.count()
    total_mous = MOU.query.count()

    partner_types = _group_count(Partner, Partner.partner_type, PARTNER_TYPES)
    partner_engagement = _group_by(Partner, Partner.engagement_level)
    moa_status_dist = _group_count(MOA, MOA.status, MOA_STATUSES)
    mou_status_dist = _group_count(MOU, MOU.status, MOU_STATUSES)

    today = date.today()
    soon = today + timedelta(days=30)
    active_states = ("Active", "Pending")
    expiring_moas = (
        MOA.query.filter(
            MOA.status.in_(active_states),
            MOA.end_date >= today,
            MOA.end_date <= soon,
        ).order_by(MOA.end_date.asc()).all()
    )
    expiring_mous = (
        MOU.query.filter(
            MOU.status.in_(active_states),
            MOU.end_date >= today,
            MOU.end_date <= soon,
        ).order_by(MOU.end_date.asc()).all()
    )

    recent_moas = MOA.query.order_by(MOA.created_at.desc()).limit(5).all()
    recent_mous = MOU.query.order_by(MOU.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard/linkages.html",
        total_partners=total_partners,
        active_partners=active_partners,
        total_moas=total_moas,
        total_mous=total_mous,
        partner_types=partner_types,
        partner_engagement=partner_engagement,
        moa_status_dist=moa_status_dist,
        mou_status_dist=mou_status_dist,
        expiring_moas=expiring_moas,
        expiring_mous=expiring_mous,
        recent_moas=recent_moas,
        recent_mous=recent_mous,
        MOA_STATUSES=MOA_STATUSES,
        MOU_STATUSES=MOU_STATUSES,
        PARTNER_TYPES=PARTNER_TYPES,
    )