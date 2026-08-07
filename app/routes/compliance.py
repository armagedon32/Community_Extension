"""Automated report generation for compliance bodies.

Presents the extension portfolio as evidence tailored to the reporting needs
of CHED, AACCUP, PACUCOA, ISO, and the SDGs. Each report pulls live data from
the database, maps it to the body's typical requirements, and adds an
interpretation of how the numbers support institutional compliance.
"""
from flask import Blueprint, abort, render_template
from flask_login import login_required

from app import db
from app.models import (
    BENEFICIARY_SEGMENTS,
    PROJECT_STATUSES,
    AccomplishmentReport,
    Activity,
    Beneficiary,
    MOA,
    Partner,
    Project,
)

compliance_bp = Blueprint("compliance", __name__)

BODIES = [
    {
        "code": "ched",
        "name": "CHED",
        "label": "Commission on Higher Education",
        "description": "Evidence of extension and institutional linkage activity supporting CHED requirements on community engagement.",
        "focus": "Instruction, research, and extension integration with documented community reach.",
    },
    {
        "code": "aaccup",
        "name": "AACCUP",
        "label": "AACCUP",
        "description": "Portfolio evidence supporting extension, research, and linkages accreditation criteria.",
        "focus": "Extension programs, community outreach, and institutional linkages.",
    },
    {
        "code": "pacucoa",
        "name": "PACUCOA",
        "label": "PACUCOA",
        "description": "Documentation of extension programs, partnerships, and outcomes for private HEI accreditation.",
        "focus": "Extension service record, partnerships, and documented outcomes.",
    },
    {
        "code": "iso",
        "name": "ISO",
        "label": "ISO",
        "description": "Process documentation demonstrating a managed, auditable approach to community extension services.",
        "focus": "Documented processes, records, and continuous monitoring.",
    },
    {
        "code": "sdg",
        "name": "SDG",
        "label": "SDG",
        "description": "Mapping of extension activities and beneficiaries to the relevant Sustainable Development Goals.",
        "focus": "Alignment of extension outcomes with the SDGs.",
    },
]


def _portfolio():
    """Gather the live compliance-relevant figures from the database."""
    return {
        "projects_total": Project.query.count(),
        "projects_by_status": {
            s: Project.query.filter_by(status=s).count() for s in PROJECT_STATUSES
        },
        "beneficiaries_total": Beneficiary.query.count(),
        "beneficiaries_by_segment": {
            s: Beneficiary.query.filter_by(segment=s).count()
            for s in BENEFICIARY_SEGMENTS
        },
        "partners_total": Partner.query.count(),
        "moas_total": MOA.query.count(),
        "activities_completed": Activity.query.filter_by(status="Completed").count(),
        "accomplishments_total": AccomplishmentReport.query.count(),
        "beneficiaries_served": AccomplishmentReport.query.with_entities(
            db.func.coalesce(db.func.sum(AccomplishmentReport.beneficiaries_served), 0)
        ).scalar() or 0,
    }


def _sdg_mapping(data):
    """Map portfolio data to representative SDGs."""
    seg = data["beneficiaries_by_segment"]
    return [
        {"sdg": "SDG 1 — No Poverty", "matched": "Livelihood & Women-led segments", "count": seg.get("Women-led Households", 0) + seg.get("Farmers", 0)},
        {"sdg": "SDG 4 — Quality Education", "matched": "Students & Youth segments", "count": seg.get("Students", 0) + seg.get("Youth", 0)},
        {"sdg": "SDG 3 — Good Health and Well-being", "matched": "Senior Citizens & General Community", "count": seg.get("Senior Citizens", 0) + seg.get("General Community", 0)},
        {"sdg": "SDG 10 — Reduced Inequalities", "matched": "IP & PWD segments", "count": seg.get("Indigenous Peoples", 0) + seg.get("PWD", 0)},
    ]


@compliance_bp.route("/reports/compliance")
@login_required
def index():
    data = _portfolio()
    return render_template("compliance/index.html", bodies=BODIES, data=data)


@compliance_bp.route("/reports/compliance/<code>")
@login_required
def report(code):
    body = next((b for b in BODIES if b["code"] == code), None)
    if body is None:
        abort(404)
    data = _portfolio()
    mapping = _sdg_mapping(data) if code == "sdg" else []
    return render_template(
        "compliance/report.html", body=body, data=data, sdg_mapping=mapping
    )