from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    PARTNER_TYPES,
    Donation,
    Partner,
    Project,
    FinancialTransaction,
    TRANSACTION_TYPES,
)

finance_bp = Blueprint("finance", __name__)


def _parse_date(value):
    if not value:
        return datetime.utcnow().date()
    return datetime.strptime(value, "%Y-%m-%d").date()


@finance_bp.route("/finance")
@login_required
def dashboard():
    contributions = (
        db.session.query(db.func.coalesce(db.func.sum(FinancialTransaction.amount), 0))
        .filter(FinancialTransaction.transaction_type == "Contribution")
        .scalar() or 0
    )
    expenses = (
        db.session.query(db.func.coalesce(db.func.sum(FinancialTransaction.amount), 0))
        .filter(FinancialTransaction.transaction_type == "Expense")
        .scalar() or 0
    )
    allocated = (
        db.session.query(db.func.coalesce(db.func.sum(FinancialTransaction.amount), 0))
        .filter(FinancialTransaction.transaction_type == "Allocation")
        .scalar() or 0
    )
    contributions = float(contributions or 0)
    expenses = float(expenses or 0)
    allocated = float(allocated or 0)

    available = contributions - expenses - allocated
    transactions = FinancialTransaction.query.order_by(
        FinancialTransaction.transaction_date.desc()
    ).limit(10).all()

    # Stakeholder donations summary
    stakeholder_total = (
        db.session.query(db.func.coalesce(db.func.sum(Donation.amount), 0)).scalar() or 0
    )
    active_funds = FinancialTransaction.query.filter_by(status="Active").count()

    return render_template(
        "finance/dashboard.html",
        contributions=contributions,
        expenses=expenses,
        allocated=allocated,
        available=available,
        allocated_funds=active_funds,
        stakeholder_total=float(stakeholder_total or 0),
        recent=transactions,
        TRANSACTION_TYPES=TRANSACTION_TYPES,
    )


@finance_bp.route("/finance/transactions")
@login_required
def transactions():
    transactions = FinancialTransaction.query.order_by(
        FinancialTransaction.transaction_date.desc()
    ).all()
    return render_template(
        "finance/transactions.html",
        transactions=transactions,
        TRANSACTION_TYPES=TRANSACTION_TYPES,
    )


@finance_bp.route("/finance/transactions/new", methods=["GET", "POST"])
@login_required
def new_transaction():
    projects = Project.query.order_by(Project.title).all()
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        if not description:
            flash("Description is required.", "danger")
            return render_template(
                "finance/transaction_form.html", transaction=None, projects=projects, TRANSACTION_TYPES=TRANSACTION_TYPES
            )
        try:
            amount = float(request.form.get("amount", 0) or 0)
        except ValueError:
            amount = 0
        tx = FinancialTransaction(
            description=description,
            transaction_type=request.form.get("transaction_type", "Contribution"),
            amount=amount,
            project_id=request.form.get("project_id") or None,
            transaction_date=_parse_date(request.form.get("transaction_date")),
            status=request.form.get("status", "Active"),
            remarks=request.form.get("remarks", ""),
            recorded_by=current_user.id,
        )
        db.session.add(tx)
        db.session.commit()
        flash("Transaction recorded successfully.", "success")
        return redirect(url_for("finance.dashboard"))

    return render_template(
        "finance/transaction_form.html", transaction=None, projects=projects, TRANSACTION_TYPES=TRANSACTION_TYPES
    )


@finance_bp.route("/finance/stakeholders")
@login_required
def stakeholders():
    partners = Partner.query.order_by(Partner.name).all()
    donations = Donation.query.order_by(Donation.payment_date.desc()).all()
    return render_template(
        "finance/stakeholders.html",
        partners=partners,
        donations=donations,
        PARTNER_TYPES=PARTNER_TYPES,
    )


@finance_bp.route("/finance/stakeholders/new", methods=["POST"])
@login_required
def add_stakeholder():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Stakeholder name is required.", "danger")
        return redirect(url_for("finance.stakeholders"))
    partner = Partner(
        name=name,
        partner_type=request.form.get("partner_type", "Other"),
        status="Active",
        engagement_level="Medium",
        contact_person=request.form.get("contact_person", ""),
        contact_number=request.form.get("contact_number", ""),
        email=request.form.get("email", ""),
        address=request.form.get("address", ""),
    )
    db.session.add(partner)
    db.session.commit()
    flash("Stakeholder added successfully.", "success")
    return redirect(url_for("finance.stakeholders"))


@finance_bp.route("/finance/donations/new", methods=["POST"])
@login_required
def new_donation():
    partner_id = request.form.get("partner_id")
    if not partner_id:
        flash("Please select a stakeholder.", "danger")
        return redirect(url_for("finance.stakeholders"))
    try:
        amount = float(request.form.get("amount", 0) or 0)
    except ValueError:
        amount = 0
    donation = Donation(
        partner_id=partner_id,
        amount=amount,
        payment_date=_parse_date(request.form.get("payment_date")),
        remarks=request.form.get("remarks", ""),
    )
    db.session.add(donation)
    db.session.commit()
    # Also reflect as a contribution transaction
    partner = db.session.get(Partner, partner_id)
    tx = FinancialTransaction(
        description=f"Donation from {partner.name}" if partner else "Stakeholder donation",
        transaction_type="Contribution",
        amount=amount,
        transaction_date=donation.payment_date,
        recorded_by=current_user.id,
    )
    db.session.add(tx)
    db.session.commit()
    flash("Donation recorded successfully.", "success")
    return redirect(url_for("finance.stakeholders"))