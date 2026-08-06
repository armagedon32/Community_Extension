from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    Member,
    MemberContribution,
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

    # Member contributions summary
    member_total = (
        db.session.query(db.func.coalesce(db.func.sum(MemberContribution.amount), 0)).scalar() or 0
    )
    active_funds = FinancialTransaction.query.filter_by(status="Active").count()

    return render_template(
        "finance/dashboard.html",
        contributions=contributions,
        expenses=expenses,
        allocated=allocated,
        available=available,
        allocated_funds=active_funds,
        member_total=float(member_total or 0),
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


@finance_bp.route("/finance/members")
@login_required
def members():
    members = Member.query.order_by(Member.name).all()
    contributions = MemberContribution.query.order_by(MemberContribution.payment_date.desc()).all()
    return render_template("finance/members.html", members=members, contributions=contributions)


@finance_bp.route("/finance/members/new", methods=["POST"])
@login_required
def new_member():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Member name is required.", "danger")
        return redirect(url_for("finance.members"))
    member = Member(
        name=name,
        employee_id=request.form.get("employee_id", ""),
        department=request.form.get("department", ""),
        email=request.form.get("email", ""),
        status="Active",
    )
    db.session.add(member)
    db.session.commit()
    flash("Member added successfully.", "success")
    return redirect(url_for("finance.members"))


@finance_bp.route("/finance/contributions/new", methods=["POST"])
@login_required
def new_contribution():
    member_id = request.form.get("member_id")
    if not member_id:
        flash("Please select a member.", "danger")
        return redirect(url_for("finance.members"))
    try:
        amount = float(request.form.get("amount", 0) or 0)
    except ValueError:
        amount = 0
    contribution = MemberContribution(
        member_id=member_id,
        amount=amount,
        payment_date=_parse_date(request.form.get("payment_date")),
        remarks=request.form.get("remarks", ""),
    )
    db.session.add(contribution)
    db.session.commit()
    # Also reflect as a contribution transaction
    member = db.session.get(Member, member_id)
    tx = FinancialTransaction(
        description=f"Member contribution — {member.name}" if member else "Member contribution",
        transaction_type="Contribution",
        amount=amount,
        transaction_date=contribution.payment_date,
        recorded_by=current_user.id,
    )
    db.session.add(tx)
    db.session.commit()
    flash("Contribution recorded successfully.", "success")
    return redirect(url_for("finance.members"))