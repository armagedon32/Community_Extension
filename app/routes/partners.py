from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import MOA, Partner, PARTNER_TYPES, SUPPORT_TYPES

partners_bp = Blueprint("partners", __name__)


@partners_bp.route("/partners")
@login_required
def list_partners():
    support_filter = request.args.get("support_type", "").strip()
    query = Partner.query
    if support_filter:
        query = query.filter(Partner.support_type == support_filter)
    partners = query.order_by(Partner.name).all()
    return render_template(
        "partners/list.html",
        partners=partners,
        PARTNER_TYPES=PARTNER_TYPES,
        SUPPORT_TYPES=SUPPORT_TYPES,
        support_filter=support_filter,
    )


@partners_bp.route("/partners/new", methods=["GET", "POST"])
@login_required
def create_partner():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Partner name is required.", "danger")
            return render_template("partners/form.html", partner=None, PARTNER_TYPES=PARTNER_TYPES)
        partner = Partner(
            name=name,
            partner_type=request.form.get("partner_type", "LGU"),
            support_type=request.form.get("support_type", "") or None,
            status=request.form.get("status", "Active"),
            engagement_level=request.form.get("engagement_level", ""),
            contact_person=request.form.get("contact_person", ""),
            contact_number=request.form.get("contact_number", ""),
            email=request.form.get("email", ""),
            address=request.form.get("address", ""),
            contribution=request.form.get("contribution", ""),
            notes=request.form.get("notes", ""),
        )
        db.session.add(partner)
        db.session.commit()
        flash("Partner added successfully.", "success")
        return redirect(url_for("partners.view_partner", partner_id=partner.id))

    return render_template("partners/form.html", partner=None, PARTNER_TYPES=PARTNER_TYPES, SUPPORT_TYPES=SUPPORT_TYPES)


@partners_bp.route("/partners/<int:partner_id>")
@login_required
def view_partner(partner_id):
    partner = db.get_or_404(Partner, partner_id)
    moas = MOA.query.filter_by(partner_id=partner.id).all()
    return render_template("partners/view.html", partner=partner, moas=moas)


@partners_bp.route("/partners/<int:partner_id>/edit", methods=["GET", "POST"])
@login_required
def edit_partner(partner_id):
    partner = db.get_or_404(Partner, partner_id)
    if request.method == "POST":
        partner.name = request.form.get("name", partner.name).strip()
        partner.partner_type = request.form.get("partner_type", partner.partner_type)
        partner.support_type = request.form.get("support_type", "") or None
        partner.status = request.form.get("status", partner.status)
        partner.engagement_level = request.form.get("engagement_level", "")
        partner.contact_person = request.form.get("contact_person", "")
        partner.contact_number = request.form.get("contact_number", "")
        partner.email = request.form.get("email", "")
        partner.address = request.form.get("address", "")
        partner.contribution = request.form.get("contribution", "")
        partner.notes = request.form.get("notes", "")
        db.session.commit()
        flash("Partner updated successfully.", "success")
        return redirect(url_for("partners.view_partner", partner_id=partner.id))

    return render_template("partners/form.html", partner=partner, PARTNER_TYPES=PARTNER_TYPES, SUPPORT_TYPES=SUPPORT_TYPES)


@partners_bp.route("/partners/<int:partner_id>/delete", methods=["POST"])
@login_required
def delete_partner(partner_id):
    partner = db.get_or_404(Partner, partner_id)
    db.session.delete(partner)
    db.session.commit()
    flash("Partner deleted.", "info")
    return redirect(url_for("partners.list_partners"))