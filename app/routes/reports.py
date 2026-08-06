from datetime import datetime
from io import BytesIO

from flask import Blueprint, Response, flash, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models import (
    AccomplishmentReport,
    Activity,
    Beneficiary,
    MOA,
    Partner,
    Project,
    PROJECT_CATEGORIES,
    PROJECT_STATUSES,
)

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports")
@login_required
def index():
    return render_template(
        "reports/index.html",
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
        PROJECT_STATUSES=PROJECT_STATUSES,
    )


@reports_bp.route("/reports/projects")
@login_required
def projects_report():
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    query = Project.query
    if status and status in PROJECT_STATUSES:
        query = query.filter(Project.status == status)
    if category and category in PROJECT_CATEGORIES:
        query = query.filter(Project.category == category)
    projects = query.order_by(Project.status, Project.title).all()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("reports/projects.html", projects=projects, generated_at=generated_at)


@reports_bp.route("/reports/beneficiaries")
@login_required
def beneficiaries_report():
    beneficiaries = Beneficiary.query.order_by(Beneficiary.segment, Beneficiary.full_name).all()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("reports/beneficiaries.html", beneficiaries=beneficiaries, generated_at=generated_at)


@reports_bp.route("/reports/partners")
@login_required
def partners_report():
    partners = Partner.query.order_by(Partner.partner_type, Partner.name).all()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("reports/partners.html", partners=partners, generated_at=generated_at)


@reports_bp.route("/reports/activities")
@login_required
def activities_report():
    activities = Activity.query.order_by(Activity.schedule_date.desc()).all()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("reports/activities.html", activities=activities, generated_at=generated_at)


@reports_bp.route("/reports/moas")
@login_required
def moas_report():
    moas = MOA.query.order_by(MOA.created_at.desc()).all()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("reports/moas.html", moas=moas, generated_at=generated_at)


@reports_bp.route("/reports/accomplishments")
@login_required
def accomplishments_report():
    reports = AccomplishmentReport.query.order_by(AccomplishmentReport.report_date.desc()).all()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("reports/accomplishments.html", reports=reports, generated_at=generated_at)


@reports_bp.route("/reports/summary.csv")
@login_required
def summary_csv():
    import csv

    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["CELMIS Summary Report", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])
    writer.writerow(["Projects"])
    writer.writerow(["Status", "Count"])
    for status, count in db.session.query(Project.status, func.count(Project.id)).group_by(Project.status).all():
        writer.writerow([status, count])
    writer.writerow([])
    writer.writerow(["Partners by Type"])
    writer.writerow(["Type", "Count"])
    for ptype, count in db.session.query(Partner.partner_type, func.count(Partner.id)).group_by(Partner.partner_type).all():
        writer.writerow([ptype, count])
    writer.writerow([])
    writer.writerow(["Beneficiaries by Segment"])
    writer.writerow(["Segment", "Count"])
    for seg, count in db.session.query(Beneficiary.segment, func.count(Beneficiary.id)).group_by(Beneficiary.segment).all():
        writer.writerow([seg, count])

    content = buffer.getvalue()
    buffer.close()
    csv_bytes = "\ufeff".encode("utf-8") + content.encode("utf-8")
    return Response(csv_bytes, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=celmis_summary.csv"})