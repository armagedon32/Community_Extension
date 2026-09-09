from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.finance_policy import (
    APPROVAL_TIERS,
    can_approve,
    can_reject,
    can_verify,
    tier_for_amount,
    tier_max_amount,
)
from app.models import (
    PARTNER_TYPES,
    Donation,
    Partner,
    Project,
    FinancialTransaction,
    TRANSACTION_TYPES,
)

finance_bp = Blueprint("finance", __name__)


@finance_bp.context_processor
def inject_finance_policy():
    return {
        "MAX_TRANSACTION_AMOUNT": current_app.config["MAX_TRANSACTION_AMOUNT"],
        "APPROVAL_TIERS": APPROVAL_TIERS,
        "tier_for_amount": tier_for_amount,
        "tier_max_amount": tier_max_amount,
        "can_verify": can_verify,
        "can_approve": can_approve,
        "can_reject": can_reject,
    }


def _parse_date(value):
    if not value:
        return datetime.utcnow().date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def _validate_amount(raw_value, max_amount):
    """Validate an amount. Returns (amount, error_message)."""
    try:
        amount = float(raw_value or 0)
    except (TypeError, ValueError):
        return 0, "Amount is invalid. Please enter a valid number."
    if amount <= 0:
        return 0, "Amount must be greater than zero."
    if amount > max_amount:
        return 0, (
            "Amount exceeds the maximum allowable transaction amount of "
            f"\u20b1 {max_amount:,.2f}."
        )
    return amount, None


@finance_bp.route("/finance")
@login_required
def dashboard():
    approved = FinancialTransaction.status == "Approved"
    contributions = (
        db.session.query(db.func.coalesce(db.func.sum(FinancialTransaction.amount), 0))
        .filter(approved, FinancialTransaction.transaction_type == "Contribution")
        .scalar() or 0
    )
    expenses = (
        db.session.query(db.func.coalesce(db.func.sum(FinancialTransaction.amount), 0))
        .filter(approved, FinancialTransaction.transaction_type == "Expense")
        .scalar() or 0
    )
    allocated = (
        db.session.query(db.func.coalesce(db.func.sum(FinancialTransaction.amount), 0))
        .filter(approved, FinancialTransaction.transaction_type == "Allocation")
        .scalar() or 0
    )
    contributions = float(contributions or 0)
    expenses = float(expenses or 0)
    allocated = float(allocated or 0)

    available = contributions - expenses - allocated
    transactions = (
        FinancialTransaction.query.order_by(
            FinancialTransaction.transaction_date.desc()
        ).limit(10).all()
    )

    # Stakeholder donations summary
    stakeholder_total = (
        db.session.query(db.func.coalesce(db.func.sum(Donation.amount), 0)).scalar() or 0
    )
    approved_funds = FinancialTransaction.query.filter_by(status="Approved").count()

    # Transactions awaiting review
    awaiting = (
        FinancialTransaction.query.filter(
            FinancialTransaction.status.in_(["Pending", "Verified"])
        )
        .order_by(FinancialTransaction.transaction_date.asc())
        .all()
    )
    pending_count = FinancialTransaction.query.filter_by(status="Pending").count()
    verified_count = FinancialTransaction.query.filter_by(status="Verified").count()

    # Per-stakeholder donation breakdown (top donors first)
    donor_rows = (
        db.session.query(
            Partner.name,
            db.func.coalesce(db.func.sum(Donation.amount), 0).label("total"),
        )
        .join(Donation, Donation.partner_id == Partner.id)
        .group_by(Partner.id)
        .order_by(db.func.sum(Donation.amount).desc())
        .all()
    )
    donors = [
        {"name": name, "total": float(total or 0)}
        for name, total in donor_rows
    ]

    return render_template(
        "finance/dashboard.html",
        contributions=contributions,
        expenses=expenses,
        allocated=allocated,
        available=available,
        allocated_funds=approved_funds,
        stakeholder_total=float(stakeholder_total or 0),
        donors=donors,
        recent=transactions,
        awaiting=awaiting,
        pending_count=pending_count,
        verified_count=verified_count,
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
    max_amount = current_app.config["MAX_TRANSACTION_AMOUNT"]

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        if not description:
            flash("Description is required.", "danger")
        else:
            amount, error = _validate_amount(
                request.form.get("amount"), max_amount
            )
            if error:
                flash(error, "danger")
            else:
                tx = FinancialTransaction(
                    description=description,
                    transaction_type=request.form.get("transaction_type", "Contribution"),
                    amount=amount,
                    project_id=request.form.get("project_id") or None,
                    transaction_date=_parse_date(request.form.get("transaction_date")),
                    status="Pending",
                    remarks=request.form.get("remarks", ""),
                    recorded_by=current_user.id,
                )
                db.session.add(tx)
                db.session.commit()
                flash(
                    "Transaction recorded and submitted for verification/approval (Pending).",
                    "success",
                )
                return redirect(url_for("finance.dashboard"))

    return render_template(
        "finance/transaction_form.html",
        transaction=None,
        projects=projects,
        TRANSACTION_TYPES=TRANSACTION_TYPES,
        max_amount=max_amount,
    )


@finance_bp.route("/finance/transactions/<int:tx_id>/verify", methods=["POST"])
@login_required
def verify_transaction(tx_id):
    tx = db.session.get(FinancialTransaction, tx_id) or abort(404)
    if tx.status != "Pending":
        flash("Only Pending transactions can be verified.", "warning")
    elif not can_verify(current_user, tx.amount):
        flash("You are not authorized to verify a transaction of this amount.", "danger")
    else:
        tx.status = "Verified"
        tx.verifier_id = current_user.id
        tx.verified_at = datetime.utcnow()
        db.session.commit()
        flash(
            f"Transaction #{tx.id} verified by {current_user.full_name}.",
            "success",
        )
    return redirect(url_for("finance.transactions"))


@finance_bp.route("/finance/transactions/<int:tx_id>/approve", methods=["POST"])
@login_required
def approve_transaction(tx_id):
    tx = db.session.get(FinancialTransaction, tx_id) or abort(404)
    if tx.status not in ("Pending", "Verified"):
        flash("Only Pending or Verified transactions can be approved.", "warning")
    elif not can_approve(current_user, tx.amount):
        flash("You are not authorized to approve a transaction of this amount.", "danger")
    else:
        tx.status = "Approved"
        tx.approver_id = current_user.id
        tx.approved_at = datetime.utcnow()
        if not tx.verifier_id:
            tx.verifier_id = current_user.id
            tx.verified_at = datetime.utcnow()
        db.session.commit()
        flash(
            f"Transaction #{tx.id} approved by {current_user.full_name}.",
            "success",
        )
    return redirect(url_for("finance.transactions"))


@finance_bp.route("/finance/transactions/<int:tx_id>/reject", methods=["POST"])
@login_required
def reject_transaction(tx_id):
    tx = db.session.get(FinancialTransaction, tx_id) or abort(404)
    if tx.status not in ("Pending", "Verified"):
        flash("Only Pending or Verified transactions can be rejected.", "warning")
    elif not can_reject(current_user, tx.amount):
        flash("You are not authorized to reject a transaction of this amount.", "danger")
    else:
        reason = request.form.get("rejection_reason", "").strip()
        if not reason:
            flash("A rejection reason is required.", "danger")
        else:
            tx.status = "Rejected"
            tx.rejected_by = current_user.id
            tx.rejected_at = datetime.utcnow()
            tx.rejection_reason = reason
            db.session.commit()
            flash(
                f"Transaction #{tx.id} rejected by {current_user.full_name}.",
                "success",
            )
    return redirect(url_for("finance.transactions"))


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
    max_amount = current_app.config["MAX_TRANSACTION_AMOUNT"]
    if not partner_id:
        flash("Please select a stakeholder.", "danger")
        return redirect(url_for("finance.stakeholders"))
    amount, error = _validate_amount(request.form.get("amount"), max_amount)
    if error:
        flash(error, "danger")
        return redirect(url_for("finance.stakeholders"))
    donation = Donation(
        partner_id=partner_id,
        amount=amount,
        payment_date=_parse_date(request.form.get("payment_date")),
        remarks=request.form.get("remarks", ""),
    )
    db.session.add(donation)
    db.session.commit()
    # Also reflect as a contribution transaction (goes through the same workflow)
    partner = db.session.get(Partner, partner_id)
    tx = FinancialTransaction(
        description=f"Donation from {partner.name}" if partner else "Stakeholder donation",
        transaction_type="Contribution",
        amount=amount,
        transaction_date=donation.payment_date,
        status="Pending",
        recorded_by=current_user.id,
    )
    db.session.add(tx)
    db.session.commit()
    flash("Donation recorded successfully. The corresponding contribution is Pending approval.", "success")
    return redirect(url_for("finance.stakeholders"))