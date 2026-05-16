from sqlalchemy import and_, or_

from app import db
from app.models import (
    Task,
    TeamMember,
    User,
    Wager,
    WagerParticipant,
    WagerTask,
)
from app.time_utils import today_app_date


POINTS_PER_TASK = 10


def _task_user_filter(user_id):
    """
    Match tasks that should count as this user's own contribution.

    Rule:
    - If a task is assigned to someone, only the assignee gets the points.
    - If a task has no assignee, the creator gets the points.
    """
    return or_(
        Task.assigned_to_user_id == user_id,
        and_(
            Task.assigned_to_user_id.is_(None),
            Task.user_id == user_id,
        ),
    )


def user_owns_or_is_assigned_task(task, user_id):
    """Return whether a task should count as this user's own contribution."""
    if task is None:
        return False

    assigned_to_user_id = getattr(task, "assigned_to_user_id", None)

    if assigned_to_user_id is not None:
        return assigned_to_user_id == user_id

    return task.user_id == user_id


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

    This is used for overall wager progress.
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


def calculate_wager_user_progress(wager, user_id):
    """
    Calculate one user's personal progress for a wager.

    Personal progress uses the same attribution rule as personal points:
    - assigned tasks count for the assignee only
    - unassigned tasks count for the creator only
    """
    personal_task_ids = set()
    completed_task_ids = set()

    for link in wager.linked_tasks:
        linked_task = resolve_linked_task(link, wager)

        if linked_task is None:
            continue

        if not user_owns_or_is_assigned_task(linked_task, user_id):
            continue

        personal_task_ids.add(linked_task.id)

        if linked_task.status == "done":
            completed_task_ids.add(linked_task.id)

    total_tasks = len(personal_task_ids)
    done_tasks = len(completed_task_ids)

    if total_tasks == 0:
        return 0, 0, 0

    progress_percent = min(100, int((done_tasks / total_tasks) * 100))
    return total_tasks, done_tasks, progress_percent


def calculate_wager_points_for_user(wager, user_id):
    """Calculate points a specific user earned from one wager."""
    _total_tasks, done_tasks, _progress_percent = calculate_wager_user_progress(
        wager,
        user_id,
    )

    return done_tasks * POINTS_PER_TASK


def count_completed_linked_tasks_for_user(user_id, team_ids=None):
    """
    Count completed linked tasks that belong to a user.

    This is used for leaderboard and personal points.
    It counts assigned tasks for the assignee, and unassigned tasks for the creator.
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
    """Calculate participant status for team-level or personal wager progress."""
    today = today_app_date()

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

    Team status is shared at the wager level, but participant progress,
    status, and rewards are based on each participant's own linked tasks.
    """
    total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)

    team_status = calculate_participant_status(
        done_tasks,
        total_tasks,
        wager.end_date,
    )

    if team_status == "completed":
        wager_status = "completed"
    elif team_status == "failed":
        wager_status = "failed"
    else:
        wager_status = "active"

    changed = False

    if wager.status != wager_status:
        wager.status = wager_status
        changed = True

    for participant in wager.participants:
        (
            personal_total_tasks,
            personal_done_tasks,
            personal_progress,
        ) = calculate_wager_user_progress(
            wager,
            participant.user_id,
        )

        personal_status = calculate_participant_status(
            personal_done_tasks,
            personal_total_tasks,
            wager.end_date,
        )

        personal_points = personal_done_tasks * POINTS_PER_TASK

        if participant.progress != personal_progress:
            participant.progress = personal_progress
            changed = True

        if participant.status != personal_status:
            participant.status = personal_status
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


def get_personal_wagers_for_user(user_id, team_ids=None):
    """
    Return wagers that personally belong to the user.

    A personal wager means the user has at least one linked task in the wager:
    - assigned tasks belong to the assignee only
    - unassigned tasks belong to the creator only

    This avoids showing every team wager just because the user is a team member
    or was added as a wager participant.
    """
    query = (
        Wager.query.join(WagerTask, WagerTask.wager_id == Wager.id)
        .join(Task, Task.id == WagerTask.task_id)
        .filter(_task_user_filter(user_id))
    )

    if team_ids is not None:
        if not team_ids:
            return []

        query = query.filter(Wager.team_id.in_(team_ids))

    return query.distinct().order_by(Wager.created_at.desc()).all()


def get_active_personal_wagers_for_user(user_id, team_ids=None):
    """
    Return active wagers that personally belong to the user.

    This should be used by personal pages such as Dashboard and Activity Feed.
    Leaders should still only see their own active wagers on those pages.
    """
    query = (
        Wager.query.join(WagerTask, WagerTask.wager_id == Wager.id)
        .join(Task, Task.id == WagerTask.task_id)
        .filter(
            Wager.status == "active",
            _task_user_filter(user_id),
        )
    )

    if team_ids is not None:
        if not team_ids:
            return []

        query = query.filter(Wager.team_id.in_(team_ids))

    return query.distinct().order_by(Wager.created_at.desc()).all()


def get_leader_team_ids(user_id):
    """Return team IDs where the user is the leader."""
    memberships = TeamMember.query.filter_by(
        user_id=user_id,
        role="leader",
    ).all()

    return [membership.team_id for membership in memberships]


def user_can_view_team_wagers(user_id):
    """Return whether the user can view team member wagers."""
    return bool(get_leader_team_ids(user_id))


def get_team_wagers_for_leader(user_id):
    """
    Return all wagers from teams led by the user.

    This should only be used on the Wager page when the leader selects the
    Team Members view.
    """
    leader_team_ids = get_leader_team_ids(user_id)

    if not leader_team_ids:
        return []

    return (
        Wager.query.filter(Wager.team_id.in_(leader_team_ids))
        .order_by(Wager.created_at.desc())
        .all()
    )


def get_wagers_for_user(user_id, team_ids=None):
    """
    Backward-compatible wrapper for personal wagers.

    By default, this now returns only wagers that personally belong to the user,
    not every wager from teams the user belongs to.
    """
    return get_personal_wagers_for_user(user_id, team_ids)


def count_wagers_won_for_user(user_id, team_ids=None):
    """Count how many team wagers a user has completed as a participant."""
    wagers = get_personal_wagers_for_user(user_id, team_ids)
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
