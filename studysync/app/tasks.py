from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Task, TeamMember

tasks_bp = Blueprint("tasks", __name__)


def validate_team_id(team_id_str):
    """Validate team_id belongs to current user."""
    if not team_id_str:
        return None, None
    try:
        team_id = int(team_id_str)
    except ValueError:
        return None, "Invalid team."
    membership = TeamMember.query.filter_by(
        team_id=team_id, user_id=current_user.id
    ).first()
    if not membership:
        return None, "You are not a member of this team."
    return team_id, None


def validate_priority(priority):
    if priority not in ("low", "medium", "high"):
        return "medium"
    return priority


@tasks_bp.route("/todos")
@login_required
def task_list():
    now = datetime.now(timezone.utc)

    tasks = (
        Task.query
        .filter_by(user_id=current_user.id)
        .order_by(Task.due_date.asc(), Task.created_at.asc())
        .all()
    )

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
    priority = validate_priority(request.form.get("priority", "medium"))
    due_date_str = request.form.get("due_date", "").strip()

    team_id, err = validate_team_id(request.form.get("team_id"))
    if err:
        flash(err, "error")
        return redirect(url_for("tasks.task_list"))

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
        team_id=team_id,
        user_id=current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    flash("Task created!", "success")
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

    team_id, err = validate_team_id(request.form.get("team_id"))
    if err:
        flash(err, "error")
        return redirect(url_for("tasks.task_list"))

    task.title = title
    task.description = request.form.get("description", "").strip() or None
    task.priority = validate_priority(request.form.get("priority", "medium"))
    task.team_id = team_id

    new_status = request.form.get("status")
    if new_status in ("todo", "in_progress", "done"):
        task.status = new_status

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