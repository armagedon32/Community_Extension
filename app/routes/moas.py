from datetime import datetime
import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import MOA, MOA_STATUSES, Partner, Project

moas_bp = Blueprint("moas", __name__)


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "jpeg"
    }


@moas_bp.route("/moas")
@login_required
def list_moas():
    status = request.args.get("status", "")
    query = MOA.query
    if status and status in MOA_STATUSES:
        query = query.filter(MOA.status == status)
    moas = query.order_by(MOA.created_at.desc()).all()
    return render_template("moas/list.html", moas=moas, MOA_STATUSES=MOA_STATUSES, current_status=status)


@moas_bp.route("/moas/new", methods=["GET", "POST"])
@login_required
def create_moa():
    partners = _get_partners()
    projects = Project.query.order_by(Project.title).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("MOA title is required.", "danger")
            return render_template("moas/form.html", moa=None, partners=partners, projects=projects,
                                   MOA_STATUSES=MOA_STATUSES)
        filename = None
        file = request.files.get("file")
        if file and file.filename:
            if _allowed_file(file.filename):
                filename = _save_upload(file)
            else:
                flash("File type not allowed.", "warning")

        moa = MOA(
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
        db.session.add(moa)
        db.session.commit()
        flash("MOA created successfully.", "success")
        return redirect(url_for("moas.list_moas"))

    return render_template("moas/form.html", moa=None, partners=partners, projects=projects, MOA_STATUSES=MOA_STATUSES)


@moas_bp.route("/moas/<int:moa_id>/edit", methods=["GET", "POST"])
@login_required
def edit_moa(moa_id):
    moa = db.get_or_404(MOA, moa_id)
    partners = _get_partners()
    projects = Project.query.order_by(Project.title).all()
    if request.method == "POST":
        moa.partner_id = request.form.get("partner_id") or None
        moa.project_id = request.form.get("project_id") or None
        moa.title = request.form.get("title", moa.title).strip()
        moa.description = request.form.get("description", "")
        moa.status = request.form.get("status", moa.status)
        moa.start_date = _parse_date(request.form.get("start_date"))
        moa.end_date = _parse_date(request.form.get("end_date"))
        moa.notes = request.form.get("notes", "")

        file = request.files.get("file")
        if file and file.filename:
            if _allowed_file(file.filename):
                moa.file_name = _save_upload(file)
            else:
                flash("File type not allowed; file not replaced.", "warning")
        db.session.commit()
        flash("MOA updated successfully.", "success")
        return redirect(url_for("moas.list_moas"))

    return render_template("moas/form.html", moa=moa, partners=partners, projects=projects, MOA_STATUSES=MOA_STATUSES)


@moas_bp.route("/moas/<int:moa_id>/delete", methods=["POST"])
@login_required
def delete_moa(moa_id):
    moa = db.get_or_404(MOA, moa_id)
    if moa.file_name:
        _delete_upload(moa.file_name)
    db.session.delete(moa)
    db.session.commit()
    flash("MOA deleted.", "info")
    return redirect(url_for("moas.list_moas"))


def _get_partners():
    # local import to avoid circular reference
    from app.models import Partner
    return Partner.query.order_by(Partner.name).all()


def _save_upload(file):
    from werkzeug.utils import secure_filename
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    filename = secure_filename(file.filename)
    if not filename:
        filename = "document"
    file.save(os.path.join(folder, filename))
    return filename


def _delete_upload(filename):
    folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(folder, os.path.basename(filename))
    if os.path.exists(path):
        os.remove(path)