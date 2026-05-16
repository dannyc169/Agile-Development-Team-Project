from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, or_

from app import db
from app.models import (
    Activity,
    Notification,
    Subtask,
    Task,
    Team,
    TeamMember,
    is_team_leader,
    is_team_member,
)
from app.time_utils import now_app_time, parse_date_as_app_time
from app.wager_helpers import sync_wagers_for_task


tasks_bp = Blueprint("tasks", __name__)


def redirect_after_task_action(default_endpoint="tasks.task_list"):
    """
    Redirect back to the page where the task action was submitted from.

    This keeps leaders on the My Teams member task page after editing tasks
    or managing subtasks there. Only internal relative paths are allowed.
    """
    return_to = request.form.get("return_to", "").strip()

    if return_to.startswith("/") and not return_to.startswith("//"):
        return redirect(return_to)

    return redirect(url_for(default_endpoint))


def can_manage_task(task, user_id):
    """
    Return whether the user can edit or delete this task.

    Task management is limited to the task creator.
    Assigned members can view and complete tasks, but cannot edit task details.
    """
    return task.user_id == user_id


def can_work_on_task(task, user_id):
    """
    Return whether the user can update task progress.

    The task creator and assigned member can update task status and subtasks.
    """
    return task.user_id == user_id or task.assigned_to_user_id == user_id


def validate_team_id(team_id_str):
    """Validate that the selected team belongs to the current user."""
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
    """Return a safe priority value."""
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
            f"from {format_status_label(old_status)} "
            f"to {format_status_label(new_status)}."
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

    This is the correct place to create activity records and sync linked wagers.
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
        Task.query.filter(
            or_(
                Task.assigned_to_user_id == current_user.id,
                and_(
                    Task.user_id == current_user.id,
                    Task.assigned_to_user_id.is_(None),
                ),
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

    # Build member lists for teams where the current user is leader.
    # This is used by the task creation assignee dropdown.
    team_members_map = {}
    for membership in memberships:
        if membership.role == "leader":
            members = TeamMember.query.filter_by(team_id=membership.team_id).all()
            team_members_map[str(membership.team_id)] = [
                {
                    "id": team_member.user_id,
                    "username": team_member.user.username,
                }
                for team_member in members
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
        is_any_leader=bool(leader_team_ids),
    )


@tasks_bp.route("/tasks/create", methods=["POST"])
@login_required
def create_task():
    is_leader = (
        TeamMember.query.filter_by(
            user_id=current_user.id,
            role="leader",
        ).first()
        is not None
    )

    if not is_leader:
        flash("Only team leaders can create tasks.", "error")
        return redirect(url_for("tasks.task_list"))

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

    if not team_id:
        flash("Tasks must be assigned to a team.", "error")
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

    assigned_to_user_id = None
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

    if assigned_to_user_id and assigned_to_user_id != current_user.id:
        db.session.add(
            Notification(
                user_id=assigned_to_user_id,
                type="task_assigned",
                message=(
                    f'{current_user.username} assigned you a new task: '
                    f'"{title}" in {team.name}.'
                ),
                link=url_for("tasks.task_list"),
            )
        )

    db.session.commit()

    flash("Task created!", "success")
    return redirect(url_for("tasks.task_list"))


@tasks_bp.route("/tasks/<int:task_id>/edit", methods=["POST"])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_manage_task(task, current_user.id):
        flash("Not authorized.", "error")
        return redirect_after_task_action()

    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required.", "error")
        return redirect_after_task_action()

    team_id, err = validate_team_id(request.form.get("team_id"))
    if err:
        flash(err, "error")
        return redirect_after_task_action()

    if not team_id:
        flash("Tasks must be assigned to a team.", "error")
        return redirect_after_task_action()

    if not is_team_leader(team_id, current_user.id):
        flash("Only team leaders can assign tasks to a team.", "error")
        return redirect_after_task_action()

    old_status = task.status

    task.title = title
    task.description = request.form.get("description", "").strip() or None
    task.team_id = team_id
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
            return redirect_after_task_action()
    else:
        task.due_date = None

    handle_task_status_change(task, old_status)

    db.session.commit()

    flash("Task updated!", "success")
    return redirect_after_task_action()


@tasks_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_work_on_task(task, current_user.id):
        flash("Not authorized.", "error")
        return redirect_after_task_action()

    old_status = task.status
    new_status = request.form.get("status")

    if new_status in ("todo", "in_progress", "done"):
        task.status = new_status
        handle_task_status_change(task, old_status)
        db.session.commit()

    return redirect_after_task_action()


@tasks_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_manage_task(task, current_user.id):
        flash("Not authorized.", "error")
        return redirect_after_task_action()

    db.session.delete(task)
    db.session.commit()

    flash("Task deleted.", "success")
    return redirect_after_task_action()


def _sync_task_status(task):
    """Sync parent task status based on subtask completion."""
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

    if not can_work_on_task(task, current_user.id):
        flash("Not authorized.", "error")
        return redirect_after_task_action()

    title = request.form.get("title", "").strip()
    if not title:
        return redirect_after_task_action()

    old_status = task.status

    db.session.add(Subtask(task_id=task.id, title=title))
    db.session.flush()

    _sync_task_status(task)
    handle_task_status_change(task, old_status)

    db.session.commit()

    return redirect_after_task_action()


@tasks_bp.route("/tasks/<int:task_id>/subtasks/<int:subtask_id>/toggle", methods=["POST"])
@login_required
def toggle_subtask(task_id, subtask_id):
    task = Task.query.get_or_404(task_id)

    if not can_work_on_task(task, current_user.id):
        flash("Not authorized.", "error")
        return redirect_after_task_action()

    subtask = Subtask.query.get_or_404(subtask_id)

    if subtask.task_id != task_id:
        flash("Not found.", "error")
        return redirect_after_task_action()

    old_status = task.status

    subtask.is_done = not subtask.is_done
    _sync_task_status(task)
    handle_task_status_change(task, old_status)

    db.session.commit()

    return redirect_after_task_action()


@tasks_bp.route("/tasks/<int:task_id>/subtasks/<int:subtask_id>/delete", methods=["POST"])
@login_required
def delete_subtask(task_id, subtask_id):
    task = Task.query.get_or_404(task_id)

    if not can_work_on_task(task, current_user.id):
        flash("Not authorized.", "error")
        return redirect_after_task_action()

    subtask = Subtask.query.get_or_404(subtask_id)

    if subtask.task_id != task_id:
        flash("Not found.", "error")
        return redirect_after_task_action()

    old_status = task.status

    db.session.delete(subtask)
    db.session.flush()

    _sync_task_status(task)
    handle_task_status_change(task, old_status)

    db.session.commit()

    return redirect_after_task_action()
