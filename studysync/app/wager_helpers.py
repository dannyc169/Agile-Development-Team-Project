from datetime import date

from sqlalchemy import or_

from app import db
from app.models import (
    Task,
    TeamMember,
    User,
    Wager,
    WagerParticipant,
    WagerTask,
)


POINTS_PER_TASK = 10


def _task_user_filter(user_id):
    """
    Match tasks that belong to a user.

    This includes:
    - tasks created by the user
    - tasks assigned to the user, if assigned_to_user_id exists in the model
    """
    filters = [Task.user_id == user_id]

    if hasattr(Task, "assigned_to_user_id"):
        filters.append(Task.assigned_to_user_id == user_id)

    return or_(*filters)


def user_owns_or_is_assigned_task(task, user_id):
    """Return whether a task should count as this user's own contribution."""
    if task is None:
        return False

    if task.user_id == user_id:
        return True

    assigned_to_user_id = getattr(task, "assigned_to_user_id", None)
    if assigned_to_user_id == user_id:
        return True

    return False


def resolve_linked_task(link, wager):
    """Get the real task linked to a wager task link."""
    if getattr(link, "task", None) is not None:
        return link.task

    task_id = getattr(link, "task_id", None)
    if task_id is not None:
        task = db.session.get(Task, task_id)
        if task is not None:
            return task

    if getattr(link, "task_name", None):
        return (
            Task.query.filter_by(
                team_id=wager.team_id,
                title=link.task_name,
            )
            .order_by(Task.created_at.desc())
            .first()
        )

    return None


def count_done_tasks_for_wager(wager):
    """
    Count completed linked tasks for a team-level wager.

    This is used for team wager progress.
    It does not represent one user's personal contribution.
    """
    done_count = 0

    for link in wager.linked_tasks:
        linked_task = resolve_linked_task(link, wager)

        if linked_task is not None and linked_task.status == "done":
            done_count += 1

    return done_count


def calculate_wager_progress(wager):
    """Calculate team-level wager progress based on linked tasks."""
    total_tasks = len(wager.linked_tasks)
    done_tasks = count_done_tasks_for_wager(wager)

    if total_tasks == 0:
        return 0, 0, 0

    progress_percent = min(100, int((done_tasks / total_tasks) * 100))
    return total_tasks, done_tasks, progress_percent


def calculate_wager_points(wager):
    """
    Calculate total team-level points earned by a wager.

    This is useful for displaying wager-level points.
    Do not use this for a user's personal total points.
    """
    _total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)
    return done_tasks * POINTS_PER_TASK


def calculate_wager_points_for_user(wager, user_id):
    """
    Calculate points a specific user earned from one wager.

    Personal points are based only on the user's own completed linked tasks:
    - created by the user, or
    - assigned to the user if assigned_to_user_id exists.
    """
    completed_task_ids = set()

    for link in wager.linked_tasks:
        linked_task = resolve_linked_task(link, wager)

        if linked_task is None:
            continue

        if linked_task.status != "done":
            continue

        if not user_owns_or_is_assigned_task(linked_task, user_id):
            continue

        completed_task_ids.add(linked_task.id)

    return len(completed_task_ids) * POINTS_PER_TASK


def count_completed_linked_tasks_for_user(user_id, team_ids=None):
    """
    Count completed linked tasks that belong to a user.

    This is used for leaderboard and personal points.
    It counts tasks created by the user and assigned to the user.
    """
    query = (
        db.session.query(Task.id)
        .join(WagerTask, WagerTask.task_id == Task.id)
        .join(Wager, Wager.id == WagerTask.wager_id)
        .join(WagerParticipant, WagerParticipant.wager_id == Wager.id)
        .filter(
            WagerParticipant.user_id == user_id,
            Task.status == "done",
            _task_user_filter(user_id),
        )
    )

    if team_ids is not None:
        if not team_ids:
            return 0

        query = query.filter(Wager.team_id.in_(team_ids))

    return query.distinct().count()


def calculate_participant_status(tasks_done, tasks_total, end_date_value):
    """Calculate participant status for a team-level wager."""
    today = date.today()

    if tasks_total > 0 and tasks_done >= tasks_total:
        return "completed"

    if end_date_value is None:
        return "on_track"

    if today > end_date_value and tasks_done < tasks_total:
        return "failed"

    days_left = (end_date_value - today).days
    if days_left <= 2 and tasks_done < tasks_total:
        return "at_risk"

    return "on_track"


def get_badge_for_points(points):
    """Return a badge based on accumulated personal points."""
    if points >= 500:
        return {
            "name": "Study Champion",
            "level": "platinum",
            "class": "bg-purple-100 text-purple-700",
        }

    if points >= 200:
        return {
            "name": "Gold Team Contributor",
            "level": "gold",
            "class": "bg-yellow-100 text-yellow-700",
        }

    if points >= 100:
        return {
            "name": "Silver Task Finisher",
            "level": "silver",
            "class": "bg-gray-100 text-gray-700",
        }

    if points >= 50:
        return {
            "name": "Bronze Study Starter",
            "level": "bronze",
            "class": "bg-orange-100 text-orange-700",
        }

    return {
        "name": "New Learner",
        "level": "none",
        "class": "bg-slate-100 text-slate-600",
    }


def sync_wager_status(wager):
    """
    Sync Wager and WagerParticipant status/progress.

    This function only updates SQLAlchemy objects.
    The caller is responsible for db.session.commit().

    Team progress is shared by all participants, but personal points are based
    on each participant's own completed linked tasks.
    """
    total_tasks, done_tasks, progress_percent = calculate_wager_progress(wager)

    participant_status = calculate_participant_status(
        done_tasks,
        total_tasks,
        wager.end_date,
    )

    if participant_status == "completed":
        wager_status = "completed"
    elif participant_status == "failed":
        wager_status = "failed"
    else:
        wager_status = "active"

    changed = False

    if wager.status != wager_status:
        wager.status = wager_status
        changed = True

    for participant in wager.participants:
        personal_points = calculate_wager_points_for_user(
            wager,
            participant.user_id,
        )

        if participant.progress != progress_percent:
            participant.progress = progress_percent
            changed = True

        if participant.status != participant_status:
            participant.status = participant_status
            changed = True

        if participant.reward_amount != personal_points:
            participant.reward_amount = personal_points
            changed = True

    return changed


def sync_wagers(wagers):
    """
    Sync multiple wagers.

    This function does not commit.
    Do not call this from GET routes just to update the database.
    """
    changed = False

    for wager in wagers:
        if sync_wager_status(wager):
            changed = True

    return changed


def sync_wagers_for_task(task):
    """
    Sync all wagers linked to this task.

    This should be called when task.status changes.
    The caller is responsible for db.session.commit().
    """
    if task is None:
        return False

    linked_rows = WagerTask.query.filter_by(task_id=task.id).all()
    wager_ids = [row.wager_id for row in linked_rows]

    if not wager_ids:
        return False

    wagers = Wager.query.filter(Wager.id.in_(wager_ids)).all()

    changed = False

    for wager in wagers:
        if sync_wager_status(wager):
            changed = True

    return changed


def user_is_wager_participant(user_id, wager_id):
    """Check whether a user is a participant of a wager."""
    participant = WagerParticipant.query.filter_by(
        wager_id=wager_id,
        user_id=user_id,
    ).first()

    return participant is not None


def get_wagers_for_user(user_id, team_ids=None):
    """
    Get wagers visible to a user.

    If team_ids is provided, only wagers in those teams are returned.
    Otherwise, return wagers from teams that the user belongs to.
    """
    if team_ids is not None:
        if not team_ids:
            return []

        return Wager.query.filter(Wager.team_id.in_(team_ids)).all()

    return (
        Wager.query.join(TeamMember, Wager.team_id == TeamMember.team_id)
        .filter(TeamMember.user_id == user_id)
        .all()
    )


def count_wagers_won_for_user(user_id, team_ids=None):
    """Count how many team wagers a user has completed as a participant."""
    wagers = get_wagers_for_user(user_id, team_ids)
    won_count = 0

    for wager in wagers:
        if not user_is_wager_participant(user_id, wager.id):
            continue

        total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)

        if total_tasks > 0 and done_tasks >= total_tasks:
            won_count += 1

    return won_count


def calculate_total_points(user_id, team_ids=None):
    """
    Calculate personal total points for a user.

    New rule:
    Each completed linked task gives POINTS_PER_TASK points.
    Only the user's own completed linked tasks count.
    """
    completed_task_count = count_completed_linked_tasks_for_user(
        user_id,
        team_ids,
    )

    return completed_task_count * POINTS_PER_TASK


def build_team_leaderboard(team_id, current_user_id=None):
    """
    Build leaderboard for one team.

    The leaderboard is team-scoped.
    It does not rank users globally across the whole system.
    """
    members = TeamMember.query.filter_by(team_id=team_id).all()
    leaderboard = []

    avatar_colors = [
        "bg-purple-500",
        "bg-pink-500",
        "bg-orange-500",
        "bg-teal-500",
        "bg-indigo-500",
        "bg-blue-500",
    ]

    for member in members:
        user = db.session.get(User, member.user_id)

        if user is None:
            continue

        completed_task_count = count_completed_linked_tasks_for_user(
            user.id,
            [team_id],
        )
        points = completed_task_count * POINTS_PER_TASK
        badge = get_badge_for_points(points)

        leaderboard.append(
            {
                "user_id": user.id,
                "name": user.username,
                "initial": user.username[:1].upper() if user.username else "?",
                "points": points,
                "badge": badge,
                "completed_task_count": completed_task_count,
                "is_current_user": user.id == current_user_id,
            }
        )

    leaderboard.sort(
        key=lambda item: (
            -item["points"],
            -item["completed_task_count"],
            item["name"].lower(),
        )
    )

    for index, item in enumerate(leaderboard):
        item["rank"] = index + 1
        item["avatar_class"] = avatar_colors[index % len(avatar_colors)]

        if item["rank"] == 1:
            item["rank_class"] = "text-yellow-600"
        elif item["rank"] == 2:
            item["rank_class"] = "text-gray-400"
        elif item["rank"] == 3:
            item["rank_class"] = "text-orange-600"
        else:
            item["rank_class"] = "text-gray-500"

    return leaderboard