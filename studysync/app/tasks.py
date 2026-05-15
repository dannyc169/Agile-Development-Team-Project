from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from sqlalchemy import or_

from app import db
from app.models import Activity, Subtask, Task, Team, TeamMember, is_team_leader, is_team_member
from app.wager_helpers import sync_wagers_for_task


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
        team_id=team_id,
        user_id=current_user.id,
    ).first()

    if not membership:
        return None, "You are not a member of this team."

    return team_id, None


def validate_priority(priority):
    if priority not in ("low", "medium", "high"):
        return "medium"

    return priority


def format_status_label(status):
    """Return a user-friendly task status label."""
    labels = {
        "todo": "Todo",
        "in_progress": "In Progress",
        "done": "Done",
    }

    return labels.get(status, status)


def create_task_status_activity(task, old_status, new_status):
    """Create an activity record when a team task status changes."""
    if task.team_id is None:
        return

    if old_status == new_status:
        return

    if new_status == "done":
        action_type = "completed_task"
        message = f"{current_user.username} completed {task.title}."
    else:
        action_type = "moved_task_status"
        message = (
            f"{current_user.username} moved {task.title} "
            f"from {format_status_label(old_status)} to {format_status_label(new_status)}."
        )

    db.session.add(
        Activity(
            user_id=current_user.id,
            team_id=task.team_id,
            task_id=task.id,
            action_type=action_type,
            message=message,
        )
    )


def handle_task_status_change(task, old_status):
    """
    Handle side effects when task.status changes.

    This is the correct place to sync related wagers.
    GET pages should only read data and should not commit sync changes.
    """
    if task.status == old_status:
        return

    create_task_status_activity(task, old_status, task.status)
    sync_wagers_for_task(task)


@tasks_bp.route("/todos")
@login_required
def task_list():
    now = datetime.now(timezone.utc)

    tasks = (
        Task.query
        .filter(
            or_(
                Task.user_id == current_user.id,
                Task.assigned_to_user_id == current_user.id,
            )
        )
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
    teams = [membership.team for membership in memberships]
    leader_team_ids = {m.team_id for m in memberships if m.role == "leader"}

    # Build member lists for teams where current user is leader (for assignee dropdown)
    team_members_map = {}
    for m in memberships:
        if m.role == "leader":
            members = TeamMember.query.filter_by(team_id=m.team_id).all()
            team_members_map[str(m.team_id)] = [
                {"id": tm.user_id, "username": tm.user.username}
                for tm in members
            ]

    return render_template(
        "todos/index.html",
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        done=done,
        teams=teams,
        team_members_map=team_members_map,
        leader_team_ids=leader_team_ids,
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
            due_date = datetime.strptime(
                due_date_str,
                "%Y-%m-%d",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("tasks.task_list"))

    # Validate team permissions and resolve assignee
    assigned_to_user_id = None
    if team_id:
        team = Team.query.get(team_id)
        if team is None:
            flash("Selected team not found.", "error")
            return redirect(url_for("tasks.task_list"))
        if not is_team_member(team_id, current_user.id):
            flash("Not authorized to assign tasks to this team.", "error")
            return redirect(url_for("tasks.task_list"))
        if not is_team_leader(team_id, current_user.id):
            flash("Only team leaders can assign tasks to a team.", "error")
            return redirect(url_for("tasks.task_list"))

        assignee_id_str = request.form.get("assigned_to_user_id", "").strip()
        if assignee_id_str:
            try:
                assignee_id = int(assignee_id_str)
            except ValueError:
                flash("Invalid assignee.", "error")
                return redirect(url_for("tasks.task_list"))
            if not is_team_member(team_id, assignee_id):
                flash("Assignee is not a member of this team.", "error")
                return redirect(url_for("tasks.task_list"))
            assigned_to_user_id = assignee_id

    task = Task(
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        team_id=team_id,
        user_id=current_user.id,
        assigned_to_user_id=assigned_to_user_id,
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

    old_status = task.status

    task.title = title
    task.description = request.form.get("description", "").strip() or None
    task.team_id = team_id
    if task.user_id == current_user.id:
        task.priority = validate_priority(request.form.get("priority", "medium"))

    new_status = request.form.get("status")
    if new_status in ("todo", "in_progress", "done"):
        task.status = new_status

    due_date_str = request.form.get("due_date", "").strip()
    if due_date_str:
        try:
            task.due_date = datetime.strptime(
                due_date_str,
                "%Y-%m-%d",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("tasks.task_list"))
    else:
        task.due_date = None

    handle_task_status_change(task, old_status)

    db.session.commit()

    flash("Task updated!", "success")
    return redirect(url_for("tasks.task_list"))


@tasks_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id and task.assigned_to_user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("tasks.task_list"))

    old_status = task.status
    new_status = request.form.get("status")

    if new_status in ("todo", "in_progress", "done"):
        task.status = new_status
        handle_task_status_change(task, old_status)
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


def _sync_task_status(task):
    subtasks = task.subtasks

    if not subtasks:
        task.status = "todo"
        return

    done_count = sum(1 for subtask in subtasks if subtask.is_done)

    if done_count == 0:
        task.status = "todo"
    elif done_count == len(subtasks):
        task.status = "done"
    else:
        task.status = "in_progress"


@tasks_bp.route("/tasks/<int:task_id>/subtasks", methods=["POST"])
@login_required
def add_subtask(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id and task.assigned_to_user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("tasks.task_list"))

    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("tasks.task_list"))

    old_status = task.status

    db.session.add(Subtask(task_id=task.id, title=title))
    db.session.flush()

    _sync_task_status(task)
    handle_task_status_change(task, old_status)

    db.session.commit()

    return redirect(url_for("tasks.task_list"))


@tasks_bp.route("/tasks/<int:task_id>/subtasks/<int:subtask_id>/toggle", methods=["POST"])
@login_required
def toggle_subtask(task_id, subtask_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id and task.assigned_to_user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("tasks.task_list"))

    subtask = Subtask.query.get_or_404(subtask_id)

    if subtask.task_id != task_id:
        flash("Not found.", "error")
        return redirect(url_for("tasks.task_list"))

    old_status = task.status

    subtask.is_done = not subtask.is_done
    _sync_task_status(task)
    handle_task_status_change(task, old_status)

    db.session.commit()

    return redirect(url_for("tasks.task_list"))


@tasks_bp.route("/tasks/<int:task_id>/subtasks/<int:subtask_id>/delete", methods=["POST"])
@login_required
def delete_subtask(task_id, subtask_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id and task.assigned_to_user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("tasks.task_list"))

    subtask = Subtask.query.get_or_404(subtask_id)

    if subtask.task_id != task_id:
        flash("Not found.", "error")
        return redirect(url_for("tasks.task_list"))

    old_status = task.status

    db.session.delete(subtask)
    db.session.flush()

    _sync_task_status(task)
    handle_task_status_change(task, old_status)

    db.session.commit()

    return redirect(url_for("tasks.task_list"))
