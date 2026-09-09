from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import MOU, MOU_STATUSES, Partner, Project
from app.routes.moas import _delete_upload, _parse_date, _save_upload, _allowed_file

mous_bp = Blueprint("mous", __name__)


@mous_bp.route("/mous")
@login_required
def list_mous():
    status = request.args.get("status", "")
    query = MOU.query
    if status and status in MOU_STATUSES:
        query = query.filter(MOU.status == status)
    mous = query.order_by(MOU.created_at.desc()).all()
    return render_template("mous/list.html", mous=mous, MOU_STATUSES=MOU_STATUSES, current_status=status)


@mous_bp.route("/mous/new", methods=["GET", "POST"])
@login_required
def create_mou():
    partners = Partner.query.order_by(Partner.name).all()
    projects = Project.query.order_by(Project.title).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("MOU title is required.", "danger")
            return render_template("mous/form.html", mou=None, partners=partners, projects=projects,
                                   MOU_STATUSES=MOU_STATUSES)
        filename = None
        file = request.files.get("file")
        if file and file.filename:
            if _allowed_file(file.filename):
                filename = _save_upload(file)
            else:
                flash("File type not allowed.", "warning")

        mou = MOU(
            partner_id=request.form.get("partner_id") or None,
            project_id=request.form.get("project_id") or None,
            title=title,
            description=request.form.get("description", ""),
            status=request.form.get("status", "Draft"),
            start_date=_parse_date(request.form.get("start_date")),
            end_date=_parse_date(request.form.get("end_date")),
            file_name=filename,
            notes=request.form.get("notes", ""),
        )
        db.session.add(mou)
        db.session.commit()
        flash("MOU created successfully.", "success")
        return redirect(url_for("mous.list_mous"))

    return render_template("mous/form.html", mou=None, partners=partners, projects=projects, MOU_STATUSES=MOU_STATUSES)


@mous_bp.route("/mous/<int:mou_id>/edit", methods=["GET", "POST"])
@login_required
def edit_mou(mou_id):
    mou = db.get_or_404(MOU, mou_id)
    partners = Partner.query.order_by(Partner.name).all()
    projects = Project.query.order_by(Project.title).all()
    if request.method == "POST":
        mou.partner_id = request.form.get("partner_id") or None
        mou.project_id = request.form.get("project_id") or None
        mou.title = request.form.get("title", mou.title).strip()
        mou.description = request.form.get("description", "")
        mou.status = request.form.get("status", mou.status)
        mou.start_date = _parse_date(request.form.get("start_date"))
        mou.end_date = _parse_date(request.form.get("end_date"))
        mou.notes = request.form.get("notes", "")

        file = request.files.get("file")
        if file and file.filename:
            if _allowed_file(file.filename):
                mou.file_name = _save_upload(file)
            else:
                flash("File type not allowed; file not replaced.", "warning")
        db.session.commit()
        flash("MOU updated successfully.", "success")
        return redirect(url_for("mous.list_mous"))

    return render_template("mous/form.html", mou=mou, partners=partners, projects=projects, MOU_STATUSES=MOU_STATUSES)


@mous_bp.route("/mous/<int:mou_id>/delete", methods=["POST"])
@login_required
def delete_mou(mou_id):
    mou = db.get_or_404(MOU, mou_id)
    if mou.file_name:
        _delete_upload(mou.file_name)
    db.session.delete(mou)
    db.session.commit()
    flash("MOU deleted.", "info")
    return redirect(url_for("mous.list_mous"))