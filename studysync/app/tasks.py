from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Task, Team, TeamMember

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/todos")
@login_required
def task_list():
    now = datetime.now(timezone.utc)

    tasks = Task.query.filter_by(user_id=current_user.id).all()

    overdue, due_today, upcoming, done = [], [], [], []

    for task in tasks:
        if task.status == "done":
            done.append(task)
        elif task.due_date is None:
            upcoming.append(task)
        elif task.due_date.date() < now.date():
            overdue.append(task)
        elif task.due_date.date() == now.date():
            due_today.append(task)
        else:
            upcoming.append(task)

    # Get teams the user belongs to (for the "Assign to Team" dropdown)
    memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
    teams = [m.team for m in memberships]

    return render_template(
        "todos/index.html",
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        done=done,
        teams=teams,
    )


@tasks_bp.route("/tasks/create", methods=["POST"])
@login_required
def create_task():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("tasks.task_list"))

    description = request.form.get("description", "").strip() or None
    priority = request.form.get("priority", "medium")
    due_date_str = request.form.get("due_date", "").strip()
    team_id = request.form.get("team_id") or None

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("tasks.task_list"))

    task = Task(
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        team_id=int(team_id) if team_id else None,
        user_id=current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    flash("Task created!", "success")
    return redirect(url_for("tasks.task_list"))


@tasks_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("tasks.task_list"))

    new_status = request.form.get("status")
    if new_status in ("todo", "in_progress", "done"):
        task.status = new_status
        db.session.commit()
    return redirect(url_for("tasks.task_list"))


@tasks_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("tasks.task_list"))

    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("tasks.task_list"))



@tasks_bp.route("/tasks/<int:task_id>/edit", methods=["POST"])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("tasks.task_list"))

    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("tasks.task_list"))

    task.title = title
    task.description = request.form.get("description", "").strip() or None
    task.priority = request.form.get("priority", "medium")
    team_id = request.form.get("team_id") or None
    task.team_id = int(team_id) if team_id else None

    due_date_str = request.form.get("due_date", "").strip()
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("tasks.task_list"))
    else:
        task.due_date = None

    db.session.commit()
    flash("Task updated!", "success")
    return redirect(url_for("tasks.task_list"))