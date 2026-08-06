from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import ACTIVITY_STATUSES, Activity, Project

activities_bp = Blueprint("activities", __name__)


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_time(value):
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


@activities_bp.route("/activities")
@login_required
def list_activities():
    activities = Activity.query.order_by(Activity.schedule_date.desc()).all()
    return render_template("activities/list.html", activities=activities, ACTIVITY_STATUSES=ACTIVITY_STATUSES)


@activities_bp.route("/activities/new", methods=["GET", "POST"])
@login_required
def create_activity():
    projects = Project.query.order_by(Project.title).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Activity title is required.", "danger")
            return render_template("activities/form.html", activity=None, projects=projects,
                                   ACTIVITY_STATUSES=ACTIVITY_STATUSES)
        try:
            participants = int(request.form.get("participants", 0) or 0)
        except ValueError:
            participants = 0
        activity = Activity(
            project_id=request.form.get("project_id") or None,
            title=title,
            description=request.form.get("description", ""),
            schedule_date=_parse_date(request.form.get("schedule_date")),
            start_time=_parse_time(request.form.get("start_time")),
            end_time=_parse_time(request.form.get("end_time")),
            location=request.form.get("location", ""),
            status=request.form.get("status", "Scheduled"),
            participants=participants,
            contact_person=request.form.get("contact_person", ""),
        )
        db.session.add(activity)
        db.session.commit()
        flash("Activity scheduled successfully.", "success")
        return redirect(url_for("activities.list_activities"))

    return render_template("activities/form.html", activity=None, projects=projects, ACTIVITY_STATUSES=ACTIVITY_STATUSES)


@activities_bp.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
def edit_activity(activity_id):
    activity = db.get_or_404(Activity, activity_id)
    projects = Project.query.order_by(Project.title).all()
    if request.method == "POST":
        try:
            participants = int(request.form.get("participants", 0) or 0)
        except ValueError:
            participants = 0
        activity.project_id = request.form.get("project_id") or None
        activity.title = request.form.get("title", activity.title).strip()
        activity.description = request.form.get("description", "")
        activity.schedule_date = _parse_date(request.form.get("schedule_date"))
        activity.start_time = _parse_time(request.form.get("start_time"))
        activity.end_time = _parse_time(request.form.get("end_time"))
        activity.location = request.form.get("location", "")
        activity.status = request.form.get("status", activity.status)
        activity.participants = participants
        activity.contact_person = request.form.get("contact_person", "")
        db.session.commit()
        flash("Activity updated successfully.", "success")
        return redirect(url_for("activities.list_activities"))

    return render_template("activities/form.html", activity=activity, projects=projects, ACTIVITY_STATUSES=ACTIVITY_STATUSES)


@activities_bp.route("/activities/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete_activity(activity_id):
    activity = db.get_or_404(Activity, activity_id)
    db.session.delete(activity)
    db.session.commit()
    flash("Activity deleted.", "info")
    return redirect(url_for("activities.list_activities"))