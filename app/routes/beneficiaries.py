from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import (
    BENEFICIARY_SEGMENTS,
    Beneficiary,
    BeneficiaryGroup,
    Project,
)

beneficiaries_bp = Blueprint("beneficiaries", __name__)


@beneficiaries_bp.route("/beneficiaries")
@login_required
def list_beneficiaries():
    beneficiaries = Beneficiary.query.order_by(Beneficiary.created_at.desc()).all()
    groups = BeneficiaryGroup.query.order_by(BeneficiaryGroup.name).all()
    return render_template(
        "beneficiaries/list.html",
        beneficiaries=beneficiaries,
        groups=groups,
        BENEFICIARY_SEGMENTS=BENEFICIARY_SEGMENTS,
    )


@beneficiaries_bp.route("/beneficiaries/new", methods=["GET", "POST"])
@login_required
def create_beneficiary():
    projects = Project.query.order_by(Project.title).all()
    groups = BeneficiaryGroup.query.order_by(BeneficiaryGroup.name).all()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("Beneficiary name is required.", "danger")
            return render_template("beneficiaries/form.html", beneficiary=None, projects=projects,
                                   groups=groups, BENEFICIARY_SEGMENTS=BENEFICIARY_SEGMENTS)
        try:
            age = int(request.form.get("age")) if request.form.get("age") else None
        except ValueError:
            age = None
        beneficiary = Beneficiary(
            project_id=request.form.get("project_id") or None,
            group_id=request.form.get("group_id") or None,
            full_name=full_name,
            segment=request.form.get("segment", ""),
            sex=request.form.get("sex"),
            age=age,
            address=request.form.get("address", ""),
            contact=request.form.get("contact", ""),
            occupation=request.form.get("occupation", ""),
            notes=request.form.get("notes", ""),
        )
        db.session.add(beneficiary)
        db.session.commit()
        flash("Beneficiary added successfully.", "success")
        return redirect(url_for("beneficiaries.list_beneficiaries"))

    return render_template("beneficiaries/form.html", beneficiary=None, projects=projects, groups=groups,
                           BENEFICIARY_SEGMENTS=BENEFICIARY_SEGMENTS)


@beneficiaries_bp.route("/beneficiaries/<int:beneficiary_id>/edit", methods=["GET", "POST"])
@login_required
def edit_beneficiary(beneficiary_id):
    beneficiary = db.get_or_404(Beneficiary, beneficiary_id)
    projects = Project.query.order_by(Project.title).all()
    groups = BeneficiaryGroup.query.order_by(BeneficiaryGroup.name).all()
    if request.method == "POST":
        try:
            age = int(request.form.get("age")) if request.form.get("age") else None
        except ValueError:
            age = None
        beneficiary.project_id = request.form.get("project_id") or None
        beneficiary.group_id = request.form.get("group_id") or None
        beneficiary.full_name = request.form.get("full_name", beneficiary.full_name).strip()
        beneficiary.segment = request.form.get("segment")
        beneficiary.sex = request.form.get("sex")
        beneficiary.age = age
        beneficiary.address = request.form.get("address", "")
        beneficiary.contact = request.form.get("contact", "")
        beneficiary.occupation = request.form.get("occupation", "")
        beneficiary.notes = request.form.get("notes", "")
        db.session.commit()
        flash("Beneficiary updated successfully.", "success")
        return redirect(url_for("beneficiaries.list_beneficiaries"))

    return render_template("beneficiaries/form.html", beneficiary=beneficiary, projects=projects, groups=groups,
                           BENEFICIARY_SEGMENTS=BENEFICIARY_SEGMENTS)


@beneficiaries_bp.route("/beneficiaries/<int:beneficiary_id>/delete", methods=["POST"])
@login_required
def delete_beneficiary(beneficiary_id):
    beneficiary = db.get_or_404(Beneficiary, beneficiary_id)
    db.session.delete(beneficiary)
    db.session.commit()
    flash("Beneficiary deleted.", "info")
    return redirect(url_for("beneficiaries.list_beneficiaries"))