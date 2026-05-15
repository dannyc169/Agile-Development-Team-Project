from datetime import date

from app import db
from app.models import (
    Task,
    Team,
    TeamMember,
    User,
    Wager,
    WagerParticipant,
    WagerTask,
)


POINTS_PER_TASK = 10


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
    """Count how many linked tasks of this wager are completed."""
    done_count = 0

    for link in wager.linked_tasks:
        linked_task = resolve_linked_task(link, wager)

        if linked_task is not None and linked_task.status == "done":
            done_count += 1

    return done_count


def calculate_wager_progress(wager):
    """Calculate wager task progress based on linked tasks."""
    total_tasks = len(wager.linked_tasks)
    done_tasks = count_done_tasks_for_wager(wager)

    if total_tasks == 0:
        return 0, 0, 0

    progress_percent = min(100, int((done_tasks / total_tasks) * 100))
    return total_tasks, done_tasks, progress_percent


def calculate_wager_points(wager):
    """
    Calculate points earned from a wager.

    Current rule:
    Each completed linked task gives 10 points.
    For team-level wagers, all participants share the same progress and points.
    """
    _total_tasks, done_tasks, _progress_percent = calculate_wager_progress(wager)

    return done_tasks * POINTS_PER_TASK


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


def calculate_reward_amount(status, stake_amount):
    """
    Legacy helper kept for older route/template code.

    New points logic should use calculate_wager_points(wager).
    This function is kept temporarily so older imports do not break.
    """
    if status == "completed":
        return stake_amount

    if status in {"on_track", "at_risk"}:
        return stake_amount

    return 0


def get_badge_for_points(points):
    """Return a badge based on accumulated points."""
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

    Important:
    reward_amount is currently used as the stored points field for compatibility.
    The actual points rule is fixed:
    1 completed linked task = 10 points.
    """
    total_tasks, done_tasks, progress_percent = calculate_wager_progress(wager)
    points_earned = calculate_wager_points(wager)

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
        if participant.progress != progress_percent:
            participant.progress = progress_percent
            changed = True

        if participant.status != participant_status:
            participant.status = participant_status
            changed = True

        if participant.reward_amount != points_earned:
            participant.reward_amount = points_earned
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
    """Count how many wagers a user has completed."""
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
    Calculate total wager points for a user.

    New rule:
    Each completed linked task gives 10 points.
    stake_amount is no longer used for points calculation.
    """
    wagers = get_wagers_for_user(user_id, team_ids)
    total_points = 0

    for wager in wagers:
        if not user_is_wager_participant(user_id, wager.id):
            continue

        total_points += calculate_wager_points(wager)

    return total_points


def build_team_leaderboard(team_id, current_user_id=None):
    """
    Build leaderboard for one team.

    The leaderboard is team-scoped.
    It does not rank users globally across the whole system.
    """
    members = TeamMember.query.filter_by(team_id=team_id).all()
    leaderboard = []

    for member in members:
        user = db.session.get(User, member.user_id)

        if user is None:
            continue

        points = calculate_total_points(user.id, [team_id])
        badge = get_badge_for_points(points)

        completed_task_count = Task.query.filter(
            Task.user_id == user.id,
            Task.team_id == team_id,
            Task.status == "done",
        ).count()

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

    return leaderboard


def build_team_leaderboards(team_ids, current_user_id=None):
    """
    Build leaderboards for multiple teams.

    This is useful when a user belongs to multiple teams.
    The feed page can display one team leaderboard at a time.
    """
    team_leaderboards = []

    for team_id in team_ids:
        team = db.session.get(Team, team_id)

        if team is None:
            continue

        team_leaderboards.append(
            {
                "team_id": team.id,
                "team_name": team.name,
                "leaderboard": build_team_leaderboard(
                    team.id,
                    current_user_id=current_user_id,
                ),
            }
        )

    return team_leaderboards